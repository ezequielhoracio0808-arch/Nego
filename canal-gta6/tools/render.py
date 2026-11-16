#!/usr/bin/env python3
"""Renderiza los vídeos del canal a partir de guiones/videos.json.

Uso:  python3 tools/render.py [id ...]      (sin ids = todos)
Necesita: ffmpeg, piper-tts, Pillow, numpy y la voz Piper indicada en PIPER_VOICE.
Salida: salida/<id>-<slug>/{video.mp4, miniatura.jpg, subtitulos.srt, descripcion.txt}
"""
import json, math, os, re, subprocess, sys, wave, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "tools", "fonts")
OUT = os.path.join(ROOT, "salida")
VOICE = os.environ.get("PIPER_VOICE", "")
CHANNEL = os.environ.get("CANAL", "MODO LEONIDA")
W, H, FPS = 1920, 1080, 30
HORIZON = 640
GAP = 0.45  # silencio tras cada escena (s)

F_HEAD = os.path.join(FONTS, "anton-latin-400-normal.woff")
F_BOLD = os.path.join(FONTS, "inter-latin-800-normal.woff")
F_REG = os.path.join(FONTS, "inter-latin-400-normal.woff")

# Pronunciación para la voz (los subtítulos usan el texto original)
PRON = [
    (r"GTA V\b", "GTA cinco"), (r"GTA 6", "GTA seis"), (r"GTA VI", "GTA seis"),
    (r"PS5", "PlayStation cinco"), (r"PS4", "PlayStation cuatro"),
    (r"PlayStation", "Pleistéishon"), (r"Xbox One", "Equisbox Uan"), (r"Xbox", "Equisbox"),
    (r"Series X", "Síries Equis"), (r"Series S", "Síries Ese"), (r"Series", "Síries"),
    (r"Jason", "Yéison"), (r"Bonnie y Clyde", "Boni y Claid"),
    (r"Leonida Keys", "Leonida Kis"), (r"Grassrivers", "Grasríbers"),
    (r"Port Gellhorn", "Port Guélhorn"), (r"Mount Kalaga", "Maunt Kalaga"),
    (r"Rockstar", "Rocstar"), (r"Vice City", "Váis Síti"), (r"Everglades", "Évergleids"),
    (r"Red Dead Redemption", "Red Ded Redémpshon"), (r"GTA Online", "GTA onlain"),
    (r"online", "onlain"), (r"YouTube", "Yutub"), (r"glitches", "glíches"),
    (r"hacks", "jacs"), (r"mods", "mods"), (r"\bPC\b", "pecé"), (r"spoilers", "espóilers"),
    (r"San Andreas", "San Andreas"), (r"GTA tres", "GTA tres"), (r"\bGTA\b", "ge te a"),
]


def pron(t):
    for a, b in PRON:
        t = re.sub(a, b, t)
    return t


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ---------------------------------------------------------------- voz
def tts(text, path):
    if not os.path.exists(path):
        subprocess.run([sys.executable, "-m", "piper", "-m", VOICE, "-f", path,
                        "--length-scale", "0.92", "--sentence-silence", "0.18"],
                       input=pron(text).encode(), check=True, capture_output=True)
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()


# ---------------------------------------------------------------- música (generada, libre de derechos)
def music(dur, path, seed):
    sr = 44100
    n = int(dur * sr) + sr
    t = np.arange(n) / sr
    bpm = 96
    beat = 60 / bpm
    prog = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]  # Am F C G
    out = np.zeros(n)
    bar = beat * 4
    f = lambda m: 440 * 2 ** ((m - 69) / 12)
    for i in range(int(dur / bar) + 2):
        ch = prog[i % 4]
        s0, s1 = int(i * bar * sr), min(n, int((i + 1) * bar * sr))
        if s0 >= n:
            break
        tt = t[s0:s1] - i * bar
        env = np.minimum(1, tt / 0.6) * np.minimum(1, (bar - tt) / 0.4)
        for m in ch:  # pad
            for det in (-0.08, 0.08):
                ph = 2 * np.pi * f(m) * (1 + det / 100) * tt
                out[s0:s1] += 0.05 * env * (np.sin(ph) + 0.3 * np.sin(2 * ph))
        for k in range(8):  # bajo en corcheas
            b0 = s0 + int(k * beat / 2 * sr)
            b1 = min(s1, b0 + int(beat / 2 * sr))
            if b0 >= b1:
                continue
            bt = t[b0:b1] - t[b0]
            out[b0:b1] += 0.16 * np.exp(-bt * 6) * np.sign(np.sin(2 * np.pi * f(ch[0] - 24) * bt)) * 0.6
        for k in range(4):  # bombo
            k0 = s0 + int(k * beat * sr)
            k1 = min(s1, k0 + int(0.25 * sr))
            if k0 >= k1:
                continue
            kt = t[k0:k1] - t[k0]
            out[k0:k1] += 0.35 * np.exp(-kt * 18) * np.sin(2 * np.pi * (50 + 90 * np.exp(-kt * 30)) * kt)
    # filtro paso bajo simple
    k = np.exp(-np.arange(64) / 6.0); k /= k.sum()  # paso bajo suave
    y = np.convolve(out, k, mode="same")
    y = y[: int(dur * sr)]
    fade = int(1.5 * sr)
    y[-fade:] *= np.linspace(1, 0, fade)
    y = y / (np.abs(y).max() + 1e-9) * 0.8
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((y * 32767).astype(np.int16).tobytes())


# ---------------------------------------------------------------- escenario
def build_sky(accent):
    acc = hex2rgb(accent)
    top, mid, low = (12, 6, 30), mix((60, 10, 80), acc, 0.35), mix((255, 120, 60), acc, 0.25)
    sky = np.zeros((H, W, 3), np.float32)
    for y in range(HORIZON):
        k = y / HORIZON
        c = mix(top, mid, k / 0.6) if k < 0.6 else mix(mid, low, (k - 0.6) / 0.4)
        sky[y] = c
    sky[HORIZON:] = (14, 6, 26)
    img = Image.fromarray(sky.astype(np.uint8))
    # sol con franjas
    sun = Image.new("RGBA", (560, 560))
    sd = ImageDraw.Draw(sun)
    for r in range(280, 0, -2):
        k = 1 - r / 280
        sd.ellipse([280 - r, 280 - r, 280 + r, 280 + r], fill=mix(mix(acc, (255, 60, 120), 0.3), (255, 225, 90), k) + (255,))
    for i in range(7):
        yy = 300 + i * 34
        sd.rectangle([0, yy, 560, yy + 4 + i * 2], fill=(0, 0, 0, 0))
    pad = 220  # el halo necesita margen para no cortarse en un rectángulo
    halo = Image.new("L", (560 + 2 * pad, 560 + 2 * pad), 0)
    ImageDraw.Draw(halo).ellipse([pad, pad, pad + 560, pad + 560], fill=170)
    halo = halo.filter(ImageFilter.GaussianBlur(70))
    glow = Image.new("RGBA", halo.size, mix(acc, (255, 140, 110), 0.4) + (0,))
    glow.putalpha(halo)
    img.paste(glow, (960 - 280 - pad, HORIZON - 420 - pad), glow)
    img.paste(sun, (960 - 280, HORIZON - 420), sun)
    # skyline
    d = ImageDraw.Draw(img)
    rnd = random.Random(7)
    x = 0
    while x < W:
        w = rnd.randint(30, 90)
        h = rnd.randint(30, 200) if abs(x - 960) > 300 else rnd.randint(20, 90)
        d.rectangle([x, HORIZON - h, x + w, HORIZON], fill=(22, 8, 40))
        for wy in range(HORIZON - h + 10, HORIZON - 6, 16):
            for wx in range(x + 6, x + w - 6, 14):
                if rnd.random() < 0.18:
                    d.rectangle([wx, wy, wx + 4, wy + 6], fill=mix(acc, (255, 230, 150), 0.5))
        x += w + rnd.randint(0, 6)
    return np.array(img)


def palm(h, flip=False, seed=0):
    rnd = random.Random(seed)
    im = Image.new("RGBA", (700, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    col = (8, 2, 16, 255)
    pts = []
    bx, top = 300, 140
    for i in range(41):
        k = i / 40
        x = bx + 90 * math.sin(k * 1.4) * (1 - k) + 60 * k
        pts.append((x, h - k * (h - top)))
    for i in range(40):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        wdt = 26 - 12 * i / 40
        d.polygon([(x0 - wdt, y0), (x0 + wdt, y0), (x1 + wdt, y1), (x1 - wdt, y1)], fill=col)
    cx, cy = pts[-1]
    for a in range(0, 360, 32):
        ang = math.radians(a + rnd.uniform(-8, 8))
        L = rnd.uniform(220, 300)
        poly = []
        for s in range(13):
            k = s / 12
            droop = 120 * k * k
            px = cx + math.cos(ang) * L * k
            py = cy + math.sin(ang) * L * k * 0.5 + droop
            poly.append((px, py, 22 * math.sin(math.pi * k) + 2))
        upper = [(px, py - w) for px, py, w in poly]
        lower = [(px, py + w) for px, py, w in reversed(poly)]
        d.polygon(upper + lower, fill=col)
    if flip:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    return im


def draw_floor(tt, grid_col):
    floor = Image.new("RGB", (W, H - HORIZON), (14, 6, 26))
    fd = ImageDraw.Draw(floor)
    fh = H - HORIZON
    off = (tt * 0.6) % 1
    for k in range(14):
        z = (k + off) / 14
        y = int(fh * z ** 2.2)
        fd.line([(0, y), (W, y)], fill=mix((14, 6, 26), grid_col, 0.25 + 0.75 * z), width=2)
    for k in range(-24, 25):
        fd.line([(960 + k * 22, 0), (960 + k * 260, fh)], fill=mix((14, 6, 26), grid_col, 0.6), width=2)
    return np.array(floor)


def fit_font(path, text, maxw, start, minsize=60):
    s = start
    while s > minsize:
        f = ImageFont.truetype(path, s)
        if f.getbbox(text)[2] <= maxw:
            return f
        s -= 6
    return ImageFont.truetype(path, minsize)


def text_layer(title, sub, accent):
    acc = hex2rgb(accent)
    f = fit_font(F_HEAD, title, 1640, 230)
    bb = f.getbbox(title)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    lay = Image.new("RGBA", (W, 560), (0, 0, 0, 0))
    x = (W - tw) // 2 - bb[0]
    y = 60 - bb[1]
    sh = Image.new("RGBA", lay.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((x + 10, y + 12), title, font=f, fill=(0, 0, 0, 200))
    sh = sh.filter(ImageFilter.GaussianBlur(14))
    lay.alpha_composite(sh)
    d = ImageDraw.Draw(lay)
    d.text((x + 6, y + 6), title, font=f, fill=acc + (255,))
    d.text((x, y), title, font=f, fill=(255, 255, 255, 255), stroke_width=4, stroke_fill=(20, 6, 30, 255))
    if sub:
        fs = ImageFont.truetype(F_BOLD, 54)
        sb = fs.getbbox(sub)
        sw = sb[2] - sb[0]
        px, py = (W - sw) // 2, 60 + th + 50
        d.rounded_rectangle([px - 34, py - 18, px + sw + 34, py + 70], 20, fill=(15, 5, 28, 225), outline=acc + (255,), width=4)
        d.text((px - sb[0], py - sb[1] + 2), sub, font=fs, fill=(255, 255, 255, 255))
    return np.array(lay)


def caption_img(text):
    f = ImageFont.truetype(F_BOLD, 50)
    bb = f.getbbox(text)
    w, h = bb[2] - bb[0], 50
    im = Image.new("RGBA", (w + 60, h + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w + 59, h + 39], 16, fill=(0, 0, 0, 170))
    d.text((30 - bb[0], 20 - bb[1] + 4), text, font=f, fill=(255, 255, 255, 255))
    return np.array(im)


def blend(frame, rgba, x, y, alpha=1.0):
    h, w = rgba.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    src = rgba[y0 - y:y1 - y, x0 - x:x1 - x]
    a = src[..., 3:4].astype(np.float32) / 255 * alpha
    dst = frame[y0:y1, x0:x1].astype(np.float32)
    frame[y0:y1, x0:x1] = (src[..., :3] * a + dst * (1 - a)).astype(np.uint8)


def chunks(text, n=7):
    words = text.split()
    out, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= n or (w[-1] in ".,?!:" and len(cur) >= 3):
            out.append(" ".join(cur)); cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def nice(t):
    t = t.lower()
    i = 1 if t[:1] in "¿¡" else 0
    t = t[:i] + t[i:i + 1].upper() + t[i + 1:]
    for w in ("gta", "pc", "ps5", "xbox", "x|s"):
        t = re.sub(rf"\b{re.escape(w)}\b", w.upper() if w != "xbox" else "Xbox", t)
    for w in ("leonida", "jason", "lucía", "vice city", "leonida keys", "grassrivers", "port gellhorn", "ambrosia", "mount kalaga", "online"):
        t = t.replace(w, w.title() if w != "online" else "Online")
    return t


def ts(s):
    ms = int(round(s * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


# ---------------------------------------------------------------- render
def render(v):
    vid = f"{v['id']}-{v['slug']}"
    od = os.path.join(OUT, vid)
    tmp = os.path.join(od, "_tmp")
    os.makedirs(tmp, exist_ok=True)
    acc = hex2rgb(v["accent"])

    # 1) voz por escena + línea de tiempo
    timeline, t = [], 0.4
    for i, sc in enumerate(v["scenes"]):
        p = os.path.join(tmp, f"s{i:02d}.wav")
        d = tts(sc["n"], p)
        timeline.append((t, d, p))
        t += d + GAP
    total = t + 0.8

    # 2) subtítulos
    caps = []
    for (st, d, _), sc in zip(timeline, v["scenes"]):
        cs = chunks(sc["n"])
        L = sum(len(c) for c in cs)
        c0 = st
        for c in cs:
            cd = d * len(c) / L
            caps.append((c0, c0 + cd, c))
            c0 += cd
    with open(os.path.join(od, "subtitulos.srt"), "w") as f:
        for i, (a, b, c) in enumerate(caps, 1):
            f.write(f"{i}\n{ts(a)} --> {ts(b)}\n{c}\n\n")

    # 3) audio: voz + música + whoosh
    music(total, os.path.join(tmp, "music.wav"), int(v["id"]))
    inputs, filt = [], []
    for i, (st, d, p) in enumerate(timeline):
        inputs += ["-i", p]
        filt.append(f"[{i}:a]aresample=44100,adelay={int(st * 1000)}:all=1[v{i}]")
    n = len(timeline)
    inputs += ["-i", os.path.join(tmp, "music.wav")]
    filt.append("".join(f"[v{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0,apad[voice]")
    filt.append(f"[{n}:a]volume=0.22[mus]")
    filt.append("[voice]asplit[vo1][vo2]")
    filt.append("[mus][vo1]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[duck]")
    filt.append(f"[vo2][duck]amix=inputs=2:normalize=0,atrim=0:{total:.3f},loudnorm=I=-14:TP=-1.5:LRA=11[out]")
    audio = os.path.join(tmp, "audio.m4a")
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filt),
                    "-map", "[out]", "-ar", "48000", "-c:a", "aac", "-b:a", "192k", audio], check=True)

    # 4) vídeo
    sky = build_sky(v["accent"])
    pl = np.array(palm(1000, False, 1)); pr = np.array(palm(860, True, 2))
    layers = [text_layer(sc["t"], sc.get("s"), v["accent"]) for sc in v["scenes"]]
    capimgs = [(a, b, caption_img(c)) for a, b, c in caps]
    logo = Image.new("RGBA", (600, 70), (0, 0, 0, 0))
    ImageDraw.Draw(logo).text((0, 0), CHANNEL, font=ImageFont.truetype(F_HEAD, 52), fill=acc + (230,))
    logo = np.array(logo)
    grid_col = mix(acc, (255, 255, 255), 0.15)

    out = os.path.join(od, "video.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-i", audio, "-map", "0:v", "-map", "1:a",
                           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                           "-c:a", "copy", "-shortest", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    nf = int(total * FPS)
    starts = [s for s, _, _ in timeline]
    for fi in range(nf):
        tt = fi / FPS
        fr = sky.copy()
        # suelo con rejilla animada
        fr[HORIZON:] = draw_floor(tt, grid_col)
        sway = int(8 * math.sin(tt * 0.7))
        blend(fr, pl, -170 + sway, H - 1000)
        blend(fr, pr, W - 560 - sway, H - 860)
        # titular de la escena
        si = max(i for i, s in enumerate(starts) if s - 0.25 <= tt) if tt >= starts[0] - 0.25 else 0
        local = tt - (starts[si] - 0.25)
        a = min(1, max(0, local / 0.35))
        ease = 1 - (1 - a) ** 3
        end = (starts[si + 1] - 0.25) if si + 1 < len(starts) else total
        out_a = min(1, max(0, (end - tt) / 0.2))
        dy = int(70 * (1 - ease) - local * 6)
        blend(fr, layers[si], 0, 130 + dy, ease * out_a)
        # flash de transición
        if 0 <= local < 0.12:
            fr = (fr.astype(np.float32) * (1 - (0.12 - local) * 3) + 255 * (0.12 - local) * 3).clip(0, 255).astype(np.uint8)
        # subtítulo
        for a0, b0, im in capimgs:
            if a0 <= tt < b0:
                blend(fr, im, (W - im.shape[1]) // 2, 930)
                break
        blend(fr, logo, 50, 36, 0.9)
        # barra de progreso
        fr[H - 10:, : int(W * tt / total)] = acc
        ff.stdin.write(fr.tobytes())
    ff.stdin.close()
    ff.wait()

    # 5) miniatura 1280x720
    base = sky.copy()
    base[HORIZON:] = draw_floor(0.3, grid_col)
    th = Image.fromarray(base).convert("RGBA")
    th.alpha_composite(Image.fromarray(pl), (-170, H - 1000))
    th.alpha_composite(Image.fromarray(pr), (W - 560, H - 860))
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 60))
    th.alpha_composite(dark)
    d = ImageDraw.Draw(th)
    l1, l2 = v["thumb"]
    f1 = fit_font(F_HEAD, l1, 1700, 330)
    f2 = fit_font(F_HEAD, l2, 1700, 330)
    for txt, f, y, col in ((l1, f1, 150, (255, 255, 255)), (l2, f2, 520, acc)):
        bb = f.getbbox(txt)
        x = (W - (bb[2] - bb[0])) // 2 - bb[0]
        d.text((x + 12, y + 12), txt, font=f, fill=(0, 0, 0, 255))
        d.text((x, y), txt, font=f, fill=col + (255,), stroke_width=10, stroke_fill=(10, 2, 20, 255))
    fb = ImageFont.truetype(F_HEAD, 72)
    bw = fb.getbbox(CHANNEL)[2]
    d.rounded_rectangle([60, 50, 60 + bw + 60, 160], 22, fill=acc + (255,))
    d.text((90, 58), CHANNEL, font=fb, fill=(10, 2, 20, 255))
    th.convert("RGB").resize((1280, 720), Image.LANCZOS).save(os.path.join(od, "miniatura.jpg"), quality=92)

    # 6) descripción para YouTube
    tl = "\n".join(f"{int(s // 60)}:{int(s % 60):02d} {nice(sc['t'])}" for (s, _, _), sc in zip(timeline, v["scenes"]))
    tl = "0:00" + tl[tl.index(" "):] if tl.startswith("0:00") else "0:00 Intro\n" + tl
    desc = (f"{v['title']}\n\n{v['scenes'][0]['n']}\n\nCapítulos:\n{tl}\n\n"
            f"Suscríbete a {CHANNEL} para guías, consejos y noticias de GTA 6 cada día.\n\n"
            f"Canal no oficial, sin relación con Rockstar Games ni Take-Two Interactive. "
            f"Grand Theft Auto es una marca de Take-Two Interactive.\n\n"
            + " ".join("#" + t.replace(" ", "") for t in v["tags"][:3]) + "\n\nEtiquetas: " + ", ".join(v["tags"]) + "\n")
    with open(os.path.join(od, "descripcion.txt"), "w") as f:
        f.write(desc)
    subprocess.run(["rm", "-rf", tmp])
    print(f"OK {vid}  {total:.1f}s")


if __name__ == "__main__":
    vids = json.load(open(os.path.join(ROOT, "guiones", "videos.json")))
    want = set(sys.argv[1:])
    for v in vids:
        if not want or v["id"] in want:
            render(v)
