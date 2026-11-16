#!/usr/bin/env python3
"""ENCENDEMOS LA CIUDAD: una ciudad con 100.000 ventanas. Cada seguidor enciende una.

La ciudad y el orden de encendido son siempre los mismos (semilla fija), así que la
ventana nº N es siempre la misma: el seguidor N "tiene" su ventana.

Comandos (desde la carpeta encendemos-la-ciudad/):
  python3 tools/ciudad.py intro                      -> salida/01-intro.mp4 + salida/01-portada.png
  python3 tools/ciudad.py perfil                     -> salida/perfil.png
  python3 tools/ciudad.py estado 12345               -> salida/estado-12345.png
  python3 tools/ciudad.py actualizacion 1000 2500    -> salida/actualizacion-1000-2500.mp4
  python3 tools/ciudad.py ventana 4218 @usuario      -> salida/ventana-4218.png
Necesita: Python 3, numpy, Pillow y ffmpeg.
"""
import math, os, random, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "salida")
FONTS = os.path.join(ROOT, "tools", "fonts")
F_HEAD = os.path.join(FONTS, "anton-latin-400-normal.woff")
F_BOLD = os.path.join(FONTS, "inter-latin-800-normal.woff")
F_REG = os.path.join(FONTS, "inter-latin-400-normal.woff")

W, H, FPS = 1080, 1920, 30
TARGET = 100_000
GROUND = 1560          # base de los edificios; debajo, el agua
TOP_LIMIT = 820        # techo de la torre más alta
SEED = 2026
WARM = (255, 196, 110)


def fmt(n):
    return f"{n:,}".replace(",", ".")


# ------------------------------------------------------------------ la ciudad
MAXH = GROUND - TOP_LIMIT


def segments(b, k):
    """Rectángulos de fachada de un edificio (con escalonamiento opcional)."""
    bx, bw, bh, setb, inset = b
    hh = min(MAXH, int(bh * k))
    top = GROUND - hh
    if setb and hh > 220:
        ys = GROUND - int(hh * setb)
        return [(bx, bx + bw, ys, GROUND), (bx + inset, bx + bw - inset, top, ys)]
    return [(bx, bx + bw, top, GROUND)]


def seg_windows(seg):
    x0, x1, y0, y1 = seg
    cols = max(0, (x1 - x0 - 5) // 2)
    rows = max(0, (y1 - y0 - 14) // 2)
    return [(x0 + 3 + c * 2, y0 + 8 + r * 2) for r in range(rows) for c in range(cols)]


def build_city():
    rng = random.Random(SEED)
    # edificios del primer plano (los que tienen las 100.000 ventanas)
    bs, x = [], 0
    while x < W:
        w = rng.randrange(18, 92, 2)
        if W - (x + w) < 18:
            w = W - x
        c = (x + w / 2) / W
        prof = 0.38 + 0.62 * math.exp(-((c - 0.5) / 0.22) ** 2)
        h = rng.uniform(0.3, 1.0) * prof
        setb = rng.uniform(0.55, 0.8) if (w >= 40 and rng.random() < 0.5) else 0
        inset = rng.randrange(4, max(6, w // 4), 2) if setb else 0
        bs.append((x, w, h, setb, inset))
        x += w + rng.choice((2, 2, 4))

    def layout(k):
        wins = []
        for bi, b in enumerate(bs):
            for seg in segments(b, k):
                wins += [(px, py, bi) for px, py in seg_windows(seg)]
        return wins

    lo, hi = 100.0, 6000.0
    for _ in range(40):  # altura mínima que da >= 100.000 ventanas
        mid = (lo + hi) / 2
        if len(layout(mid)) >= TARGET:
            hi = mid
        else:
            lo = mid
    k = hi
    wins = layout(k)
    # quitamos el sobrante de la fila más alta para que sean EXACTAMENTE 100.000
    wins.sort(key=lambda p: (p[1], p[0]))
    wins = wins[len(wins) - TARGET:]
    assert len(wins) == TARGET
    wins.sort(key=lambda p: (p[2], p[1], p[0]))
    wx = np.array([p[0] for p in wins], np.int32)
    wy = np.array([p[1] for p in wins], np.int32)
    wb = np.array([p[2] for p in wins], np.int32)

    # "habitaciones": 2-4 ventanas seguidas de la misma planta se encienden juntas
    rr = random.Random(SEED + 2)
    rooms, cur, lim = [], [0], 3
    for i in range(1, TARGET):
        if wb[i] == wb[i - 1] and wy[i] == wy[i - 1] and wx[i] == wx[i - 1] + 2 and len(cur) < lim:
            cur.append(i)
        else:
            rooms.append(cur)
            cur, lim = [i], rr.choice((2, 3, 3, 4))
    rooms.append(cur)

    # la ventana nº 1 está en una torre central, a un tercio de su altura
    cand = np.where(np.abs(wx - 540) < 60)[0]
    tops = wy[cand].min()
    hero = int(cand[np.argmin(np.abs(wy[cand] - (tops + (GROUND - tops) * 0.33)) + np.abs(wx[cand] - 540) * 0.5)])
    hr = next(ri for ri, r in enumerate(rooms) if hero in r)
    perm = [hr] + [int(p) for p in np.random.default_rng(SEED).permutation(len(rooms)) if p != hr]
    order = []
    for ri in perm:
        r = rooms[ri]
        order += ([hero] + [i for i in r if i != hero]) if ri == hr else r
    order = np.array(order, np.int32)
    assert len(order) == TARGET and len(set(order.tolist())) == TARGET

    # color de cada habitación (todas sus ventanas iguales)
    r = np.random.default_rng(SEED + 1)
    pal = np.array([(255, 200, 120), (255, 232, 190), (205, 225, 255), (130, 175, 255), (255, 170, 90)], np.float32)
    room_col = pal[r.choice(len(pal), len(rooms), p=[0.5, 0.24, 0.14, 0.05, 0.07])] * r.uniform(0.7, 1.0, (len(rooms), 1))
    cols = np.zeros((TARGET, 3), np.float32)
    for ri, rm in enumerate(rooms):
        cols[rm] = room_col[ri]
    return bs, k, wx, wy, order, cols.astype(np.uint8)


BS, K, WX, WY, ORDER, COLS = build_city()


def antennas():
    out = []
    for b in BS:
        x0, x1, y0, _ = segments(b, K)[-1]
        if GROUND - y0 > MAXH * 0.7 and x1 - x0 >= 24:
            out.append(((x0 + x1) // 2, y0 - 46))
    return out


ANTENNAS = antennas()


def sky_base(dawn=0.0):
    y = np.linspace(0, 1, H)[:, None]
    night_top, night_low = np.array([5, 6, 20.]), np.array([58, 38, 104.])
    dawn_top, dawn_low = np.array([40, 60, 120.]), np.array([255, 150, 90.])
    top = night_top * (1 - dawn) + dawn_top * dawn
    low = night_low * (1 - dawn) + dawn_low * dawn
    g = np.clip((y - 0.05) / (GROUND / H - 0.05), 0, 1) ** 1.6
    sky = top + (low - top) * g[..., None]
    img = np.repeat(sky, W, axis=1)
    rng = np.random.default_rng(7)
    n = 900
    sx, sy = rng.integers(0, W, n), (rng.random(n) ** 1.7 * (GROUND - 200)).astype(int)
    b = rng.uniform(60, 230, n) * (1 - dawn)
    img[sy, sx] = np.maximum(img[sy, sx], b[:, None])
    return img


def draw_base(dawn=0.0):
    """Cielo + luna + silueta de fondo + fachadas con las ventanas apagadas."""
    img = sky_base(dawn)
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    if dawn < 0.5:  # luna creciente
        halo = Image.new("L", (W, H), 0)
        ImageDraw.Draw(halo).ellipse([842, 840, 962, 960], fill=90)
        im.paste((150, 150, 190), (0, 0), halo.filter(ImageFilter.GaussianBlur(40)))
        mm = Image.new("L", (W, H), 0)
        md = ImageDraw.Draw(mm)
        md.ellipse([862, 860, 942, 940], fill=255)
        md.ellipse([882, 850, 962, 930], fill=0)
        im.paste((235, 232, 210), (0, 0), mm)
    if dawn > 0.5:  # sol saliendo detrás de la ciudad
        sun = Image.new("L", (W, H), 0)
        ImageDraw.Draw(sun).ellipse([170, GROUND - 330, 430, GROUND - 70], fill=255)
        halo = sun.filter(ImageFilter.GaussianBlur(90))
        im.paste((255, 170, 100), (0, 0), halo.point(lambda v: int(v * 0.8)))
        im.paste((255, 222, 150), (0, 0), sun)
    rng = random.Random(SEED + 5)
    x = -20
    back = (int(26 + 50 * dawn), int(24 + 22 * dawn), int(56 + 4 * dawn))
    while x < W:  # skyline lejano, sin ventanas
        w = rng.randrange(30, 140)
        h = rng.randrange(120, 520)
        d.rectangle([x, GROUND - 40 - h, x + w, GROUND], fill=back)
        if rng.random() < 0.3:
            d.rectangle([x + w // 2 - 1, GROUND - 40 - h - rng.randrange(20, 60), x + w // 2 + 1, GROUND - 40 - h], fill=back)
        x += w + rng.randrange(0, 12)
    arr = np.array(im).astype(np.float32)
    facade = np.array([9, 10, 24.]) * (1 - dawn) + np.array([30, 24, 40.]) * dawn
    dark = np.array([36, 42, 82.]) * (1 - dawn) + np.array([60, 52, 70.]) * dawn
    rb = random.Random(SEED + 9)
    for b in BS:
        fac = facade * rb.uniform(0.8, 1.3)
        for x0, x1, y0, y1 in segments(b, K):
            arr[y0:y1, x0:x1] = fac
            arr[y0:y1, x0] = fac * 2.0 + 3      # borde iluminado
            arr[y0, x0:x1] = fac * 1.7 + 2      # cornisa
    for ax, ay in ANTENNAS:
        arr[ay:ay + 46, ax - 1:ax + 1] = facade * 1.5
    arr[WY, WX] = dark
    return np.clip(arr, 0, 255).astype(np.uint8)


BASE = {}


def base(dawn):
    """Mezcla entre la ciudad de noche y la del amanecer (0 = noche, 1 = amanecer)."""
    for k in (0.0, 1.0):
        if k not in BASE:
            BASE[k] = draw_base(k).astype(np.float32)
    if dawn <= 0:
        return BASE[0.0].copy()
    if dawn >= 1:
        return BASE[1.0].copy()
    return BASE[0.0] * (1 - dawn) + BASE[1.0] * dawn


def world(n, t=0.0, dawn=None):
    """Imagen de la ciudad con las n primeras ventanas encendidas."""
    n = int(max(0, min(TARGET, n)))
    if dawn is None:
        dawn = 1.0 if n >= TARGET else 0.0
    img = base(dawn)
    lit = np.zeros((H, W, 3), np.float32)
    if n:
        idx = ORDER[:n]
        lit[WY[idx], WX[idx]] = COLS[idx]
    img = np.maximum(img, lit)
    # bloom
    small = lit.reshape(H // 4, 4, W // 4, 4, 3).mean((1, 3))
    sm = Image.fromarray(np.clip(small * 3.2, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2.2))
    glow = np.asarray(sm.resize((W, H), Image.BILINEAR), np.float32)
    img += glow * 0.9 * (1 - 0.6 * (n / TARGET) ** 1.5) * (1 - 0.5 * dawn)
    # contaminación lumínica: el cielo se calienta según cuántas luces hay
    f = n / TARGET
    if f > 0:
        yy = np.arange(H)[:, None]
        haze = np.clip(1 - (GROUND - yy) / 700, 0, 1) ** 2 * (yy < GROUND)
        img += haze[..., None] * np.array([70, 40, 25.]) * f * (1 - dawn)
    # luces rojas de las antenas (parpadean)
    if math.sin(t * 2.4) > -0.2:
        for ax, ay in ANTENNAS:
            img[ay - 2:ay + 1, ax - 1:ax + 2] = (255, 40, 40)
    # agua: reflejo con ondas
    hw = H - GROUND
    rows = np.arange(hw)
    src_y = GROUND - 1 - rows
    off = (np.sin(rows * 0.21 + t * 2.0) * (1 + rows * 0.03)).astype(int)
    xs = (np.arange(W)[None, :] + off[:, None]) % W
    refl = img[src_y[:, None], xs]
    fade = (0.42 * (1 - rows / hw) ** 0.8)[:, None, None]
    img[GROUND:] = refl * fade + np.array([4, 6, 16.]) * (1 - fade)
    img[GROUND:GROUND + 2] *= 0.6
    return img


def finish(img):
    return np.clip(img, 0, 255).astype(np.uint8)


# ------------------------------------------------------------------ cámara y efectos
def camera(img, z, cx, cy):
    cw, ch = W / z, H / z
    l = min(max(cx - cw / 2, 0), W - cw)
    t = min(max(cy - ch / 2, 0), H - ch)
    im = Image.fromarray(finish(img)).resize((W, H), Image.BICUBIC, box=(l, t, l + cw, t + ch))
    to_screen = lambda x, y: ((x + 0.5 - l) * z, (y + 0.5 - t) * z)
    return np.asarray(im, np.float32).copy(), to_screen


def radial(img, x, y, r, color, k):
    x0, x1 = int(max(0, x - r)), int(min(W, x + r + 1))
    y0, y1 = int(max(0, y - r)), int(min(H, y + r + 1))
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    d = np.sqrt((xx - x) ** 2 + (yy - y) ** 2) / r
    a = np.clip(1 - d, 0, 1) ** 2.2 * k
    img[y0:y1, x0:x1] += a[..., None] * np.array(color, np.float32)


def ring(im, x, y, t, label=None, sub=None):
    d = ImageDraw.Draw(im)
    r = 30 + 4 * math.sin(t * 5)
    d.ellipse([x - r, y - r, x + r, y + r], outline=WARM + (255,), width=5)
    if label:
        f = ImageFont.truetype(F_BOLD, 40)
        fs = ImageFont.truetype(F_REG, 32)
        tw = f.getbbox(label)[2]
        sw = fs.getbbox(sub)[2] if sub else 0
        bw = max(tw, sw) + 48
        bh = 70 + (44 if sub else 0)
        side = -1 if x > W / 2 else 1
        bx = x + side * (r + 40) - (bw if side < 0 else 0)
        bx = min(max(30, bx), W - 30 - bw)
        by = y - bh / 2
        d.line([x + side * r, y, bx + (bw if side < 0 else 0), y], fill=WARM + (255,), width=4)
        d.rounded_rectangle([bx, by, bx + bw, by + bh], 18, fill=(12, 10, 24, 235), outline=WARM + (255,), width=3)
        d.text((bx + 24, by + 12), label, font=f, fill=(255, 255, 255))
        if sub:
            d.text((bx + 24, by + 66), sub, font=fs, fill=WARM)


def fit(path, text, maxw, size):
    while size > 30:
        f = ImageFont.truetype(path, size)
        if f.getbbox(text)[2] <= maxw:
            return f
        size -= 4
    return ImageFont.truetype(path, 30)


def text_block(lines, width=940):
    """lines: [(texto, 'big'|'mid'|'small', color)] -> capa RGBA centrada."""
    lay = Image.new("RGBA", (W, 700), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    y = 0
    for txt, kind, col in lines:
        if kind == "big":
            f = fit(F_HEAD, txt, width, 150)
        elif kind == "mid":
            f = fit(F_HEAD, txt, width, 96)
        else:
            f = fit(F_BOLD, txt, width, 46)
        bb = f.getbbox(txt)
        x = (W - (bb[2] - bb[0])) // 2 - bb[0]
        sh = Image.new("RGBA", lay.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((x, y - bb[1] + 6), txt, font=f, fill=(0, 0, 0, 230))
        lay.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
        d.text((x, y - bb[1]), txt, font=f, fill=col + (255,))
        y += (bb[3] - bb[1]) + (26 if kind != "small" else 20)
    return np.asarray(lay, np.float32), y


def blend(img, layer, top, alpha):
    if alpha <= 0:
        return
    lay, h = layer
    seg = lay[:min(h + 20, lay.shape[0])]
    a = seg[..., 3:4] / 255 * alpha
    y1 = min(H, top + seg.shape[0])
    img[top:y1] = seg[: y1 - top, :, :3] * a[: y1 - top] + img[top:y1] * (1 - a[: y1 - top])


def counter(im, n, y=610, label="LUCES ENCENDIDAS"):
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(F_HEAD, 104)
    fl = ImageFont.truetype(F_BOLD, 30)
    a, b = fmt(n), " / " + fmt(TARGET)
    fb = ImageFont.truetype(F_HEAD, 60)
    wa, wb = f.getbbox(a)[2], fb.getbbox(b)[2]
    x = (W - wa - wb) // 2
    d.text((x + 3, y + 4), a, font=f, fill=(0, 0, 0))
    d.text((x, y), a, font=f, fill=WARM)
    d.text((x + wa, y + 38), b, font=fb, fill=(235, 235, 245))
    lw = fl.getbbox(label)[2]
    d.text(((W - lw) // 2, y + 136), label, font=fl, fill=(200, 200, 215))


# ------------------------------------------------------------------ audio (sintetizado)
SR = 44100


def tone(f, dur, amp, attack=0.01, decay=None, kind="sine"):
    t = np.arange(int(dur * SR)) / SR
    ph = 2 * np.pi * f * t
    w = np.sin(ph) if kind == "sine" else (2 * (ph / (2 * np.pi) % 1) - 1)
    env = np.minimum(1, t / attack)
    env *= np.exp(-t / decay) if decay else np.minimum(1, (dur - t) / 0.3)
    return amp * w * env


def place(buf, sig, at):
    i = int(at * SR)
    j = min(len(buf), i + len(sig))
    if j > i:
        buf[i:j] += sig[: j - i]


def lowpass(x, n=48):
    k = np.exp(-np.arange(n) / (n / 6)); k /= k.sum()
    return np.convolve(x, k, mode="same")


def pad(total, chords, amp=0.06):
    buf = np.zeros(int(total * SR) + SR)
    seg = total / len(chords)
    for i, ch in enumerate(chords):
        for m in ch:
            f = 440 * 2 ** ((m - 69) / 12)
            for det in (0.997, 1.003):
                s = tone(f * det, seg + 1.2, amp, attack=0.8, kind="saw")
                place(buf, lowpass(s, 90), i * seg)
    return buf


def click(buf, at):
    n = np.random.default_rng(3).normal(0, 1, int(0.03 * SR)) * np.exp(-np.arange(int(0.03 * SR)) / 120)
    place(buf, 0.5 * n, at)
    place(buf, tone(1760, 1.6, 0.12, decay=0.5) + tone(2637, 1.6, 0.07, decay=0.35), at + 0.02)


def riser(buf, at, dur):
    t = np.arange(int(dur * SR)) / SR
    f = 120 + 900 * (t / dur) ** 2
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * (t / dur) ** 2 * 0.18
    nz = lowpass(np.random.default_rng(4).normal(0, 1, len(t)), 6) * (t / dur) ** 3 * 0.25
    place(buf, s + nz, at)


def boom(buf, at):
    t = np.arange(int(1.8 * SR)) / SR
    place(buf, 0.7 * np.sin(2 * np.pi * (42 + 60 * np.exp(-t * 8)) * t) * np.exp(-t * 2.2), at)


def write_audio(buf, path):
    buf = buf / (np.abs(buf).max() + 1e-9) * 0.89
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((buf * 32767).astype(np.int16).tobytes())


# ------------------------------------------------------------------ salida de vídeo
def encoder(path, audio, total):
    return subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-i", audio, "-map", "0:v", "-map", "1:a",
                             "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
                             "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.2f}", "-movflags", "+faststart", path],
                            stdin=subprocess.PIPE)


def ease(a):
    a = min(1, max(0, a))
    return a * a * (3 - 2 * a)


def fade(t, a, b, f=0.3):
    return min(1, max(0, (t - a) / f)) * min(1, max(0, (b - t) / f))


# ------------------------------------------------------------------ comandos
def cmd_intro():
    total = 21.0
    hx, hy = int(WX[ORDER[0]]), int(WY[ORDER[0]])
    T = {  # textos en pantalla
        "a": text_block([("ESTA CIUDAD TIENE", "mid", (230, 230, 240)), ("100.000 VENTANAS", "big", (255, 255, 255))]),
        "b": text_block([("Y TODAS ESTÁN", "mid", (230, 230, 240)), ("APAGADAS", "big", (255, 255, 255))]),
        "c": text_block([("HASTA HOY.", "big", WARM)]),
        "d": text_block([("CADA SEGUIDOR", "mid", (230, 230, 240)), ("ENCIENDE UNA", "big", WARM)]),
        "e": text_block([("IMAGINA CUANDO", "mid", (230, 230, 240)), ("SEAMOS 100.000", "big", (255, 255, 255))]),
        "f": text_block([("PERO HOY", "mid", (230, 230, 240)), ("SOLO HAY UNA", "big", WARM)]),
        "g": text_block([("SIGUE Y ENCIENDE", "mid", (230, 230, 240)), ("LA TUYA", "big", WARM),
                         ("Cuando se encienda la última, amanece.", "small", (220, 220, 230))]),
    }
    schedule = [("a", 0.15, 2.9), ("b", 3.0, 5.3), ("c", 5.5, 8.6), ("d", 8.8, 11.5), ("e", 11.7, 15.5),
                ("f", 15.65, 17.6), ("g", 17.75, total + 1)]
    LIGHT, SPREAD0, SPREAD1, CUT = 5.5, 11.7, 15.2, 15.6

    # audio
    buf = pad(total, [[45, 52, 57, 59], [41, 48, 53, 57], [45, 52, 57, 59], [43, 50, 55, 59]], 0.05)
    click(buf, LIGHT)
    riser(buf, SPREAD0, CUT - SPREAD0)
    cut_i = int(CUT * SR)
    buf[cut_i:cut_i + int(0.5 * SR)] *= np.linspace(0, 1, int(0.5 * SR)) ** 2
    boom(buf, CUT)
    click(buf, 17.75)
    a = os.path.join(OUT, "_intro.wav")
    write_audio(buf[: int(total * SR)], a)

    path = os.path.join(OUT, "01-intro.mp4")
    ff = encoder(path, a, total)
    for fi in range(int(total * FPS)):
        t = fi / FPS
        # cuántas luces
        if t < LIGHT:
            n = 0
        elif SPREAD0 <= t < CUT:
            p = ease((t - SPREAD0) / (SPREAD1 - SPREAD0))
            n = max(1, int(TARGET * p ** 2.2))
        else:
            n = 1
        # cámara
        if t < 2.9:
            z, cx, cy = 1 + 0.04 * t / 2.9, W / 2, H / 2
        elif t < 5.3:
            e = ease((t - 2.9) / 2.4)
            z, cx, cy = 1.04 + 3.6 * e, W / 2 + (hx - W / 2) * e, H / 2 + (hy - H / 2) * e
        elif t < 6.9:
            z, cx, cy = 4.64 + 0.15 * (t - 5.3), hx, hy
        elif t < 8.8:
            e = ease((t - 6.9) / 1.9)
            z = 4.88 + (1.0 - 4.88) * e
            cx, cy = hx + (W / 2 - hx) * e, hy + (H / 2 - hy) * e
        else:
            z, cx, cy = 1.0 + 0.012 * (t - 8.8), W / 2, H / 2
        dawn = 0.0
        if SPREAD0 <= t < CUT:
            dawn = 0.9 * ease((t - SPREAD0 - 1.6) / (SPREAD1 - SPREAD0 - 1.2))
        img = world(n, t, dawn=dawn)
        frame, to_s = camera(img, z, cx, cy)
        if n >= 1:
            sx, sy = to_s(hx, hy)
            boost = 1.0 + (1.6 * math.exp(-(t - LIGHT) * 3) if t >= LIGHT else 0)
            radial(frame, sx, sy, 14 + 9 * z, (255, 190, 110), 0.8 * boost)
            hz = max(1.0, z) / 2
            frame[int(sy - hz):int(sy + hz) + 1, int(sx - hz / 2):int(sx + hz / 2) + 1] = (255, 222, 160)
        if LIGHT <= t < LIGHT + 0.12:
            frame += 60 * (1 - (t - LIGHT) / 0.12)
        if CUT <= t < CUT + 0.08:
            frame *= 0.2
        # textos
        for k, a0, a1 in schedule:
            al = fade(t, a0, a1, 0.25)
            if al > 0:
                blend(frame, T[k], 220 + int(30 * (1 - min(1, (t - a0) / 0.35)) ** 2), al)
        im = Image.fromarray(finish(frame))
        if n == 1 and t > 6.2:
            sx, sy = to_s(hx, hy)
            ring(im, sx, sy, t, "VENTANA Nº 1" if t > 8.8 else None, "la primera luz" if t > 8.8 else None)
        if t >= 8.9:
            counter(im, n)
        ff.stdin.write(im.tobytes())
    ff.stdin.close(); ff.wait()
    os.remove(a)
    # portada (para TikTok / Reels)
    frame, _ = camera(world(0, 0.5), 1.02, W / 2, H / 2)
    blend(frame, T["a"], 220, 1)
    Image.fromarray(finish(frame)).save(os.path.join(OUT, "01-portada.png"))
    print("OK", path)


def cmd_estado(n):
    n = int(n)
    img = world(n, 0.3)
    frame = img.copy()
    if n >= TARGET:
        blend(frame, text_block([("AMANECE", "big", (255, 230, 180)), ("100.000 LUCES. GRACIAS.", "mid", (255, 255, 255))]), 230, 1)
    else:
        blend(frame, text_block([("FALTAN", "mid", (230, 230, 240)), (fmt(TARGET - n), "big", WARM),
                                 ("para que amanezca", "small", (220, 220, 230))]), 230, 1)
    im = Image.fromarray(finish(frame))
    counter(im, n, y=650)
    p = os.path.join(OUT, f"estado-{n}.png")
    im.save(p)
    print("OK", p)


def cmd_actualizacion(a, b):
    a, b = int(a), int(b)
    total = 9.0
    buf = pad(total, [[45, 52, 57, 59], [41, 48, 53, 57]], 0.05)
    riser(buf, 2.0, 4.6)
    click(buf, 6.6)
    wav = os.path.join(OUT, "_upd.wav")
    write_audio(buf[: int(total * SR)], wav)
    path = os.path.join(OUT, f"actualizacion-{a}-{b}.mp4")
    ff = encoder(path, wav, total)
    t1 = text_block([("HOY SE HAN ENCENDIDO", "mid", (230, 230, 240)), (fmt(b - a) + " LUCES", "big", WARM)])
    t2 = text_block([("FALTAN " + fmt(max(0, TARGET - b)), "big", (255, 255, 255)),
                     ("para que amanezca. Sigue y enciende la tuya.", "small", (220, 220, 230))])
    for fi in range(int(total * FPS)):
        t = fi / FPS
        n = int(a + (b - a) * ease((t - 2.0) / 4.6))
        frame, _ = camera(world(n, t), 1.0 + 0.012 * t, W / 2, H / 2)
        blend(frame, t1, 220, fade(t, 0.2, 6.4))
        blend(frame, t2, 220, fade(t, 6.6, total + 1))
        im = Image.fromarray(finish(frame))
        counter(im, n)
        ff.stdin.write(im.tobytes())
    ff.stdin.close(); ff.wait()
    os.remove(wav)
    print("OK", path)


def cmd_ventana(n, user=""):
    n = int(n)
    idx = ORDER[n - 1]
    x, y = int(WX[idx]), int(WY[idx])
    frame, to_s = camera(world(n, 0.3), 3.2, x, y + 30)
    sx, sy = to_s(x, y)
    radial(frame, sx, sy, 70, (255, 190, 110), 0.9)
    frame[int(sy - 4):int(sy + 5), int(sx - 3):int(sx + 4)] = (255, 226, 165)
    blend(frame, text_block([("ESTA ES TU LUZ", "big", (255, 255, 255)), (user, "mid", WARM)] if user
                            else [("ESTA ES TU LUZ", "big", (255, 255, 255))]), 230, 1)
    im = Image.fromarray(finish(frame))
    ring(im, sx, sy, 0.4, f"VENTANA Nº {fmt(n)}", f"de {fmt(TARGET)}")
    p = os.path.join(OUT, f"ventana-{n}.png")
    im.save(p)
    print("OK", p)


def cmd_perfil():
    S = 1080
    im = Image.new("RGB", (S, S))
    d = ImageDraw.Draw(im)
    for y in range(S):
        k = y / S
        d.line([(0, y), (S, y)], fill=(int(6 + 40 * k), int(7 + 22 * k), int(22 + 60 * k)))
    rng = random.Random(4)
    for _ in range(120):
        x, y = rng.randrange(S), rng.randrange(int(S * 0.55))
        v = rng.randrange(80, 220)
        d.point((x, y), fill=(v, v, v))
    d.ellipse([700, 190, 800, 290], fill=(235, 232, 210))
    d.ellipse([725, 175, 825, 275], fill=(12, 12, 32))
    towers = [(120, 300, 560), (330, 300, 330), (540, 270, 470), (720, 260, 620)]
    hero = None
    for i, (x, w, top) in enumerate(towers):
        d.rectangle([x, top, x + w, S], fill=(10, 11, 26))
        for r, yy in enumerate(range(top + 40, S - 20, 64)):
            for c, xx in enumerate(range(x + 26, x + w - 40, 56)):
                d.rectangle([xx, yy, xx + 30, yy + 40], fill=(26, 30, 58))
                if i == 1 and r == 4 and c == 2:
                    hero = (xx, yy)
    arr = np.asarray(im, np.float32).copy()
    hx, hy = hero
    radial(arr, hx + 15, hy + 20, 240, (255, 180, 100), 0.55)
    im = Image.fromarray(finish(arr))
    ImageDraw.Draw(im).rectangle([hx, hy, hx + 30, hy + 40], fill=(255, 214, 140))
    p = os.path.join(OUT, "perfil.png")
    im.save(p)
    print("OK", p)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    c, args = sys.argv[1], sys.argv[2:]
    {"intro": cmd_intro, "estado": cmd_estado, "actualizacion": cmd_actualizacion,
     "ventana": cmd_ventana, "perfil": cmd_perfil}[c](*args)
