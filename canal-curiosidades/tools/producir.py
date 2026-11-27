#!/usr/bin/env python3
"""Produce el vídeo del día a partir de un guion: voz, montaje, Short, miniaturas y textos.

Uso:  python3 tools/producir.py <guion|fecha> [--solo video short miniatura textos]
Antes: python3 tools/imagenes.py <guion>   (descarga las imágenes)
Salida: salida/<id>/
  video.mp4 (1920×1080) · short.mp4 (1080×1920, <60 s) · miniatura.jpg (1280×720) · portada-short.jpg
  descripcion.txt · descripcion-short.txt · subtitulos.srt · subtitulos-short.srt
Además: trabajo/<id>/fotogramas.jpg (fotogramas de ambos vídeos para revisarlos).
"""
import argparse, hashlib, json, math, os, random, re, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun as C

FPS = 30
XF = 0.5          # fundido entre escenas (s)
GAP_FRASE = 0.12  # silencio extra entre frases
GAP_ESCENA = 0.55  # silencio entre escenas
FONDO = (9, 13, 26)
CORTAS = set("a al de del el en la las lo los un una y o e u que con por para su sus mi se ni no te me le les nos muy más".split())


# ================================================================== audio
def leer_wav(p):
    with wave.open(p) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16), w.getframerate()


def escribir_wav(p, y, sr):
    with wave.open(p, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())


def locucion(escenas, tdir, pron):
    """Voz frase a frase. Devuelve segmentos, inicio de cada escena, duración total y wav de voz."""
    segs, starts, t = [], [], 0.35
    for i, sc in enumerate(escenas):
        starts.append(t)
        for fr in C.frases(sc["narracion"]):
            h = hashlib.sha1((fr + json.dumps(pron, sort_keys=True)).encode()).hexdigest()[:12]
            p = os.path.join(tdir, f"v_{h}.wav")
            d = C.tts(fr, p, pron)
            segs.append({"t": t, "d": d, "wav": p, "escena": i, "texto": fr})
            t += d + GAP_FRASE
        t += GAP_ESCENA - GAP_FRASE
    total = t + 0.9
    sr = leer_wav(segs[0]["wav"])[1]
    buf = np.zeros(int(total * sr) + sr, np.float32)
    for s in segs:
        a, _ = leer_wav(s["wav"])
        i0 = int(s["t"] * sr)
        buf[i0:i0 + len(a)] += a.astype(np.float32) / 32768
    vp = os.path.join(tdir, f"voz_{len(segs)}_{int(total * 1000)}.wav")
    escribir_wav(vp, buf[: int(total * sr)], sr)
    return segs, starts, total, vp


def musica(dur, path, seed):
    """Música ambiental de misterio generada aquí mismo (sin derechos de terceros)."""
    sr = 44100
    n = int(dur * sr) + sr
    rng = random.Random(seed)
    root = rng.choice([45, 46, 47, 48, 50, 52])  # nota grave (MIDI)
    prog = rng.choice([[(0, "m"), (8, "M"), (3, "M"), (10, "M")], [(0, "m"), (5, "m"), (8, "M"), (7, "M")],
                       [(0, "m"), (10, "M"), (8, "M"), (10, "M")], [(0, "m"), (3, "M"), (5, "m"), (8, "M")]])
    bpm = rng.choice([76, 80, 84, 88])
    beat = 60 / bpm
    seg = beat * 8  # cada acorde dura 2 compases
    f = lambda m: 440 * 2 ** ((m - 69) / 12)
    out = np.zeros(n, np.float32)
    patron = [rng.choice([0, 1, 2, 3]) for _ in range(8)]
    k = 0
    while k * seg < dur + seg:
        off, q = prog[k % len(prog)]
        notas = [root + off + x for x in ((0, 3, 7) if q == "m" else (0, 4, 7))]
        s0, s1 = int(k * seg * sr), min(n, int((k + 1) * seg * sr + 1.5 * sr))
        if s0 >= n:
            break
        tt = np.arange(s1 - s0) / sr
        env = np.minimum(1, tt / 1.6) * np.clip((seg + 1.5 - tt) / 1.5, 0, 1)
        for m in notas:  # colchón
            for det in (-0.0012, 0.0012):
                ph = 2 * np.pi * f(m + 12) * (1 + det) * tt
                out[s0:s1] += 0.035 * env * (np.sin(ph) + 0.25 * np.sin(2 * ph))
        out[s0:s1] += 0.10 * env * np.sin(2 * np.pi * f(notas[0] - 12) * tt)  # bajo
        if k >= 1 and k % 4 != 3:  # arpegio (con huecos para respirar)
            arp = notas + [notas[0] + 12]
            for j in range(16):
                a0 = s0 + int(j * beat / 2 * sr)
                a1 = min(n, a0 + int(1.2 * sr))
                if a0 >= n:
                    break
                at = np.arange(a1 - a0) / sr
                m = arp[patron[j % 8]] + 24
                tone = (np.sin(2 * np.pi * f(m) * at) + 0.2 * np.sin(4 * np.pi * f(m) * at)) * np.exp(-at * 4.5)
                out[a0:a1] += 0.05 * tone
        if k >= 2:  # pulso suave
            for j in (0, 4):
                b0 = s0 + int(j * beat * sr)
                b1 = min(n, b0 + int(0.3 * sr))
                if b0 >= n:
                    break
                bt = np.arange(b1 - b0) / sr
                out[b0:b1] += 0.10 * np.exp(-bt * 14) * np.sin(2 * np.pi * (48 + 60 * np.exp(-bt * 25)) * bt)
        k += 1
    eco = out.copy()  # eco sencillo
    for dly, g in ((0.375, 0.3), (0.75, 0.15)):
        d = int(dly * sr)
        eco[d:] += out[:-d] * g
    ker = np.exp(-np.arange(48) / 5.0); ker /= ker.sum()
    y = np.convolve(eco, ker, mode="same")[: int(dur * sr)]
    y[: sr] *= np.linspace(0, 1, sr)
    y[-2 * sr:] *= np.linspace(1, 0, 2 * sr)
    y = y / (np.abs(y).max() + 1e-9) * 0.8
    escribir_wav(path, y, sr)


def mezclar(voz, mus, total, out):
    filt = ("[0:a]aresample=48000,apad[vo];[1:a]aresample=48000,volume=0.20[mu];[vo]asplit[v1][v2];"
            "[mu][v1]sidechaincompress=threshold=0.02:ratio=8:attack=15:release=450[duck];"
            f"[v2][duck]amix=inputs=2:normalize=0,atrim=0:{total:.3f},loudnorm=I=-14:TP=-1.5:LRA=11[out]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", voz, "-i", mus, "-filter_complex", filt,
                    "-map", "[out]", "-ar", "48000", "-c:a", "aac", "-b:a", "192k", out], check=True)


def subtitulos(segs, maxc, mayus=False):
    caps = []
    for s in segs:
        words, chunks, cur = s["texto"].split(), [], []
        for w in words:
            if cur and len(" ".join(cur + [w])) > maxc:
                mover = []
                while len(cur) > 1 and cur[-1].lower().strip("¿¡,.") in CORTAS:
                    mover.insert(0, cur.pop())
                chunks.append(" ".join(cur))
                cur = mover
            cur.append(w)
        if cur:
            chunks.append(" ".join(cur))
        L = sum(len(c) for c in chunks)
        t0 = s["t"]
        for c in chunks:
            d = s["d"] * len(c) / L
            caps.append((t0, t0 + d, c.upper() if mayus else c))
            t0 += d
    return caps


def srt(caps, path):
    with open(path, "w", encoding="utf-8") as f:
        for i, (a, b, c) in enumerate(caps, 1):
            f.write(f"{i}\n{C.ts(a)} --> {C.ts(b)}\n{c}\n\n")


# ================================================================== gráficos
def cerradura(size, col, fondo=None):
    """Icono del canal: una cerradura (lo oculto)."""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if fondo:
        d.ellipse([0, 0, size - 1, size - 1], fill=fondo)
    s = size / 100
    d.ellipse([36 * s, 20 * s, 64 * s, 48 * s], fill=col)
    d.polygon([(43 * s, 40 * s), (57 * s, 40 * s), (63 * s, 80 * s), (37 * s, 80 * s)], fill=col)
    return im


def fondo_marca(size, acc, seed=1):
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w * 0.5) / w) ** 2 + ((yy - h * 0.42) / h) ** 2)
    glow = np.clip(1 - r * 1.6, 0, 1)[..., None] ** 2
    base = np.array(FONDO, np.float32) * (1 - glow * 0.3) + np.array(acc, np.float32) * glow * 0.22
    noise = np.random.default_rng(seed).normal(0, 4, (h, w, 1))
    return Image.fromarray(np.clip(base + noise, 0, 255).astype(np.uint8))


def cargar_base(path, size, over, acc, seed):
    W_, H_ = size
    if not path or not os.path.exists(path):
        return fondo_marca((int(W_ * over), int(H_ * over)), acc, seed)
    im = Image.open(path).convert("RGB")
    im = ImageEnhance.Color(ImageEnhance.Contrast(im).enhance(1.07)).enhance(1.06)
    if W_ > H_:
        return ImageOps.fit(im, (int(W_ * over), int(H_ * over)), Image.LANCZOS)
    bh = int(H_ * over)
    bw = int(im.width * bh / im.height)
    if bw < int(W_ * over):
        return ImageOps.fit(im, (int(W_ * over), bh), Image.LANCZOS)
    return im.resize((min(bw, int(W_ * over * 3)), bh), Image.LANCZOS) if bw > W_ * over * 3 else im.resize((bw, bh), Image.LANCZOS)


def vista(base, size, p, i, over):
    """Movimiento lento tipo «Ken Burns»: zoom y desplazamiento suaves."""
    W_, H_ = size
    BW, BH = base.size
    rnd = random.Random(i * 7919)
    zmax = over * 0.97
    z = 1 + (zmax - 1) * (p if i % 2 == 0 else 1 - p)
    vh = BH / z
    vw = vh * W_ / H_
    if vw > BW:  # imagen justa de ancho (retratos, fondo de marca): no salirse del borde
        vw = BW
        vh = vw * H_ / W_
    if W_ > H_:
        dx, dy = rnd.choice([-1, 1]) * rnd.uniform(0.4, 1), rnd.uniform(-0.5, 0.5)
        cx = BW / 2 + dx * (BW - vw) / 2 * (p * 2 - 1)
        cy = BH / 2 + dy * (BH - vh) / 2 * (p * 2 - 1)
    else:
        travel = min(BW - vw, vw * 0.9)
        cx = BW / 2 + (1 if i % 2 == 0 else -1) * (p - 0.5) * travel
        cy = BH / 2
    cx = min(max(cx, vw / 2), BW - vw / 2)
    cy = min(max(cy, vh / 2), BH - vh / 2)
    x0, y0 = max(0.0, cx - vw / 2), max(0.0, cy - vh / 2)
    box = (x0, y0, min(BW, x0 + vw), min(BH, y0 + vh))
    return np.asarray(base.resize((W_, H_), Image.BILINEAR, box=box))


def mascara(size, zonas):
    """Oscurece arriba/abajo para que el texto se lea. zonas: [(y0, y1, v0, v1)] en fracciones."""
    W_, H_ = size
    col = np.ones(H_, np.float32)
    for y0, y1, v0, v1 in zonas:
        a, b = int(y0 * H_), int(y1 * H_)
        col[a:b] = np.minimum(col[a:b], np.linspace(v0, v1, b - a))
    xx = np.linspace(-1, 1, W_)
    vig = 1 - 0.18 * xx ** 2
    m = col[:, None] * vig[None, :]
    return (m * 256).astype(np.uint16)[..., None]


def blend(frame, rgba, x, y, alpha=1.0):
    H_, W_ = frame.shape[:2]
    h, w = rgba.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W_, x + w), min(H_, y + h)
    if x1 <= x0 or y1 <= y0 or alpha <= 0:
        return
    src = rgba[y0 - y:y1 - y, x0 - x:x1 - x]
    a = src[..., 3:4].astype(np.float32) * (alpha / 255)
    dst = frame[y0:y1, x0:x1].astype(np.float32)
    frame[y0:y1, x0:x1] = (src[..., :3] * a + dst * (1 - a)).astype(np.uint8)


def texto_rgba(lines, font, fill, stroke=0, sc=(0, 0, 0), shadow=None, align="center", gap=0.12, maxw=None):
    """Bloque de texto (varias líneas) con contorno y sombra; devuelve RGBA numpy."""
    asc = font.getbbox("ÁÑg")
    lh = int((asc[3] - asc[1]) * (1 + gap))
    widths = [font.getbbox(l)[2] for l in lines]
    w = max(widths) + 2 * stroke + 60
    h = lh * len(lines) + 2 * stroke + 60
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
    d = ImageDraw.Draw(im)
    for k, (l, lw) in enumerate(zip(lines, widths)):
        x = 30 + stroke + ((w - 60 - 2 * stroke - lw) // 2 if align == "center" else 0)
        y = 30 + stroke + k * lh - asc[1]
        if shadow:
            sd.text((x + shadow[0], y + shadow[1]), l, font=font, fill=shadow[2], stroke_width=stroke, stroke_fill=shadow[2])
        d.text((x, y), l, font=font, fill=fill, stroke_width=stroke, stroke_fill=sc)
    if shadow:
        sh = sh.filter(ImageFilter.GaussianBlur(shadow[3] if len(shadow) > 3 else 6))
        sh.alpha_composite(im)
        im = sh
    return np.array(im)


def ease(x):
    x = min(1, max(0, x))
    return 1 - (1 - x) ** 3


# ================================================================== render común
def tramos(starts, total):
    vs = [0.0] + [s - 0.3 for s in starts[1:]]
    ve = vs[1:] + [total]
    return vs, [e + XF for e in ve]


def render_frames(size, total, out_mp4, audio, imgs, starts, over, pintar):
    """Genera los fotogramas (imagen en movimiento + fundidos) y llama a pintar(fr, t, escena)."""
    W_, H_ = size
    vs, ve = tramos(starts, total)
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W_}x{H_}",
                           "-r", str(FPS), "-i", "-", "-i", audio, "-map", "0:v", "-map", "1:a",
                           "-c:v", "libx264", "-preset", "medium", "-crf", "24", "-maxrate", "6M", "-bufsize", "12M", "-pix_fmt", "yuv420p",
                           "-c:a", "copy", "-shortest", "-movflags", "+faststart", out_mp4], stdin=subprocess.PIPE)
    nf = int(total * FPS)
    for fi in range(nf):
        t = fi / FPS
        i = max(k for k in range(len(vs)) if vs[k] <= t)
        p = (t - vs[i]) / (ve[i] - vs[i])
        fr = vista(imgs[i], size, p, i, over)
        if i > 0 and t < vs[i] + XF:
            prev = vista(imgs[i - 1], size, (t - vs[i - 1]) / (ve[i - 1] - vs[i - 1]), i - 1, over)
            a = ease((t - vs[i]) / XF)
            fr = (fr.astype(np.float32) * a + prev.astype(np.float32) * (1 - a)).astype(np.uint8)
        fr = np.array(fr)
        pintar(fr, t, i, vs)
        if t < 0.4:
            fr = (fr * (t / 0.4)).astype(np.uint8)
        if t > total - 0.6:
            fr = (fr * max(0, (total - t) / 0.6)).astype(np.uint8)
        ff.stdin.write(fr.tobytes())
    ff.stdin.close()
    if ff.wait():
        raise RuntimeError("ffmpeg falló")


def credito(c):
    if not c:
        return None
    autor = re.sub(r"\s+", " ", c["autor"])[:60]
    return f"Foto: {autor} · {c['licencia']} · {c['fuente']}"


# ================================================================== vídeo horizontal
def video(g, ctx):
    W_, H_, over = 1920, 1080, 1.16
    acc = ctx["acc"]
    tdir = C.trabajo(g["_id"], "voz")
    segs, starts, total, voz = locucion(g["escenas"], tdir, g.get("pron"))
    caps = subtitulos(segs, 44)
    srt(caps, os.path.join(ctx["out"], "subtitulos.srt"))
    mus = os.path.join(tdir, "musica.wav")
    musica(total, mus, ctx["seed"])
    audio = os.path.join(tdir, "audio.m4a")
    mezclar(voz, mus, total, audio)

    imgs, creds, last = [], [], None
    for i, sc in enumerate(g["escenas"]):
        spec = sc.get("imagen") or last
        last = spec
        path, c = ctx["img"](spec)
        imgs.append(cargar_base(path, (W_, H_), over, acc, i))
        creds.append(credito(c))
    m = mascara((W_, H_), [(0, 0.16, 0.6, 1), (0.58, 1, 1, 0.32)])
    f_tit = ImageFont.truetype(C.F_HEAD, 88)
    f_cap = ImageFont.truetype(C.F_BOLD, 50)
    f_cre = ImageFont.truetype(C.F_REG, 20)
    heads = []
    for sc in g["escenas"]:
        if not sc.get("titulo"):
            heads.append(None); continue
        t = texto_rgba([sc["titulo"]], f_tit, (255, 255, 255, 255), 0, shadow=(4, 6, (0, 0, 0, 200), 10), align="left")
        bar = np.zeros((t.shape[0], 14, 4), np.uint8); bar[30:-30, :, :3] = acc; bar[30:-30, :, 3] = 255
        heads.append(np.concatenate([bar, t], axis=1))
    cifras = [texto_rgba([sc["cifra"]], C.fit_font(C.F_HEAD, sc["cifra"], 1500, 300), acc + (255,), 0,
                         shadow=(0, 10, (0, 0, 0, 220), 18)) if sc.get("cifra") else None for sc in g["escenas"]]
    creimg = {c: texto_rgba([c], f_cre, (255, 255, 255, 170), 0, shadow=(1, 1, (0, 0, 0, 200), 2), align="left") for c in set(creds) if c}
    capimg = {}
    icon = np.array(cerradura(56, acc + (255,)))
    logo = texto_rgba([C.CANAL], ImageFont.truetype(C.F_HEAD, 40), (255, 255, 255, 220), 0, shadow=(2, 2, (0, 0, 0, 160), 4), align="left")

    def pintar(fr, t, i, vs):
        fr[:] = ((fr.astype(np.uint16) * m) >> 8).astype(np.uint8)
        local = t - vs[i]
        if heads[i] is not None:
            dur = (vs[i + 1] if i + 1 < len(vs) else total) - vs[i]
            a = ease((local - 0.25) / 0.45) * min(1, max(0, (min(5.0, dur - 0.3) - local) / 0.4))
            blend(fr, heads[i], 70 - int(40 * (1 - ease((local - 0.25) / 0.45))), H_ - 330, a)
        if cifras[i] is not None:
            a = ease((local - 0.4) / 0.35) * min(1, max(0, (4.6 - local) / 0.4))
            ci = cifras[i]
            blend(fr, ci, (W_ - ci.shape[1]) // 2, (H_ - ci.shape[0]) // 2 - 80, a)
        for a0, b0, c in caps:
            if a0 <= t < b0:
                if c not in capimg:
                    capimg[c] = texto_rgba([c], f_cap, (255, 255, 255, 255), 3, shadow=(0, 3, (0, 0, 0, 230), 6))
                im = capimg[c]
                blend(fr, im, (W_ - im.shape[1]) // 2, H_ - 190)
                break
        blend(fr, icon, 44, 30, 0.9)
        blend(fr, logo, 78, 12, 0.9)
        if creds[i]:
            ci = creimg[creds[i]]
            blend(fr, ci, W_ - ci.shape[1] - 10, 6, 0.85)
        fr[H_ - 6:, : int(W_ * t / total)] = acc

    out = os.path.join(ctx["out"], "video.mp4")
    render_frames((W_, H_), total, out, audio, imgs, starts, over, pintar)
    ctx["video"] = {"segs": segs, "starts": starts, "total": total}
    print(f"OK video.mp4  {total:.1f}s")


# ================================================================== short vertical
def short(g, ctx):
    S = g["short"]
    W_, H_, over = 1080, 1920, 1.12
    acc = ctx["acc"]
    tdir = C.trabajo(g["_id"], "voz")
    segs, starts, total, voz = locucion(S["escenas"], tdir, g.get("pron"))
    if total > 59.5:
        print(f"AVISO: el Short dura {total:.1f}s (>59 s). Acorta la narración del short.", file=sys.stderr)
    caps = subtitulos(segs, 16, mayus=True)
    srt(caps, os.path.join(ctx["out"], "subtitulos-short.srt"))
    mus = os.path.join(tdir, "musica-short.wav")
    musica(total, mus, ctx["seed"] + 1)
    audio = os.path.join(tdir, "audio-short.m4a")
    mezclar(voz, mus, total, audio)

    imgs, creds, last = [], [], None
    for i, sc in enumerate(S["escenas"]):
        spec = sc.get("imagen") or last
        last = spec
        path, c = ctx["img"](spec)
        imgs.append(cargar_base(path, (W_, H_), over, acc, i))
        creds.append(credito(c))
    m = mascara((W_, H_), [(0, 0.3, 0.45, 1), (0.5, 0.75, 1, 0.75), (0.75, 1, 0.75, 0.5)])
    f_cap = ImageFont.truetype(C.F_HEAD, 112)
    gancho = S.get("gancho") or g.get("miniatura")
    f_g = C.fit_font(C.F_HEAD, max(gancho, key=len), 960, 150)
    g_img = texto_rgba(gancho, f_g, (255, 255, 255, 255), 6, (10, 10, 20), shadow=(0, 8, acc + (255,), 0), gap=0.05)
    icon = np.array(cerradura(48, acc + (255,)))
    logo = texto_rgba([C.CANAL], ImageFont.truetype(C.F_HEAD, 40), (255, 255, 255, 230), 0, shadow=(2, 2, (0, 0, 0, 160), 4), align="left")
    f_cre = ImageFont.truetype(C.F_REG, 22)
    creimg = {c: texto_rgba(C.wrap(c, f_cre, 900), f_cre, (255, 255, 255, 160), 0, shadow=(1, 1, (0, 0, 0, 200), 2)) for c in set(creds) if c}
    capimg = {}

    def pintar(fr, t, i, vs):
        fr[:] = ((fr.astype(np.uint16) * m) >> 8).astype(np.uint8)
        lw = icon.shape[1] + logo.shape[1] - 30
        blend(fr, icon, (W_ - lw) // 2, 120, 0.95)
        blend(fr, logo, (W_ - lw) // 2 + icon.shape[1] - 30, 102, 0.95)
        if t < 3.2:
            a = ease(t / 0.3) * min(1, (3.2 - t) / 0.35)
            dy = int(30 * (1 - ease(t / 0.3)))
            blend(fr, g_img, (W_ - g_img.shape[1]) // 2, 250 + dy, a)
        for a0, b0, c in caps:
            if a0 <= t < b0:
                if c not in capimg:
                    lines = C.wrap(c, f_cap, 940)
                    capimg[c] = texto_rgba(lines, f_cap, (255, 255, 255, 255), 7, (0, 0, 0),
                                           shadow=(0, 9, acc + (255,), 0), gap=0.02)
                im = capimg[c]
                pop = ease((t - a0) / 0.09)
                blend(fr, im, (W_ - im.shape[1]) // 2, 1040 + int(16 * (1 - pop)), 0.4 + 0.6 * pop)
                break
        if creds[i]:
            ci = creimg[creds[i]]
            blend(fr, ci, (W_ - ci.shape[1]) // 2, 190, 0.8)

    out = os.path.join(ctx["out"], "short.mp4")
    render_frames((W_, H_), total, out, audio, imgs, starts, over, pintar)
    ctx["short"] = {"segs": segs, "starts": starts, "total": total}
    print(f"OK short.mp4  {total:.1f}s")


# ================================================================== miniaturas
def miniatura(g, ctx):
    acc = ctx["acc"]
    spec = None
    if g.get("escenas"):
        miniatura_horizontal(g, ctx)
        spec = g.get("miniatura_busqueda") or g["escenas"][g.get("miniatura_imagen", 0)].get("imagen")
    S = g.get("short")
    if S:
        portada_short(g, ctx, S, spec)
    print("OK miniaturas")


def miniatura_horizontal(g, ctx):
    acc = ctx["acc"]
    k = g.get("miniatura_imagen", 0)
    spec = g.get("miniatura_busqueda") or g["escenas"][k].get("imagen")
    path, _ = ctx["img"](spec)
    W_, H_ = 1920, 1080
    base = cargar_base(path, (W_, H_), 1.0, acc, 0).convert("RGBA")
    base = ImageEnhance.Color(ImageEnhance.Contrast(base.convert("RGB")).enhance(1.12)).enhance(1.15).convert("RGBA")
    grad = np.zeros((H_, W_, 4), np.uint8)
    xx = np.linspace(0, 1, W_)
    grad[..., 3] = (np.clip(1.25 - xx * 1.6, 0, 1) ** 1.3 * 225).astype(np.uint8)[None, :]
    grad[..., :3] = FONDO
    base.alpha_composite(Image.fromarray(grad))
    l1, l2 = g["miniatura"][0], g["miniatura"][1] if len(g["miniatura"]) > 1 else ""
    f1 = C.fit_font(C.F_HEAD, l1, 1150, 230, 90)
    f2 = C.fit_font(C.F_HEAD, l2, 1150, 260, 90) if l2 else None
    d = ImageDraw.Draw(base)
    y = 300 if l2 else 420
    for txt, f, col in ((l1, f1, (255, 255, 255)), (l2, f2, acc)):
        if not txt:
            continue
        bb = f.getbbox(txt)
        d.text((90 + 10, y + 12 - bb[1]), txt, font=f, fill=(0, 0, 0, 255), stroke_width=10, stroke_fill=(0, 0, 0, 255))
        d.text((90, y - bb[1]), txt, font=f, fill=col + (255,), stroke_width=10, stroke_fill=(8, 10, 20, 255))
        y += bb[3] - bb[1] + 46
    base.alpha_composite(cerradura(120, (10, 12, 22, 255), acc + (255,)), (W_ - 170, 50))
    base.convert("RGB").resize((1280, 720), Image.LANCZOS).save(os.path.join(ctx["out"], "miniatura.jpg"), quality=92)


def portada_short(g, ctx, S, spec):
    """Portada del Short (1080×1920)."""
    acc = ctx["acc"]
    sspec = S.get("portada_imagen") or S["escenas"][0].get("imagen") or spec
    p2, _ = ctx["img"](sspec)
    pb = cargar_base(p2, (1080, 1920), 1.0, acc, 1)
    bw = pb.width
    pb = pb.crop(((bw - 1080) // 2, 0, (bw - 1080) // 2 + 1080, 1920)).convert("RGBA")
    veil = Image.fromarray(np.dstack([np.full((1920, 1080, 3), FONDO, np.uint8),
                                      (np.clip(np.linspace(0.75, -0.4, 1920), 0, 1)[:, None] * np.ones(1080) * 230).astype(np.uint8)]))
    pb.alpha_composite(veil)
    gancho = S.get("gancho") or g.get("miniatura")
    fg = C.fit_font(C.F_HEAD, max(gancho, key=len), 960, 190)
    ti = Image.fromarray(texto_rgba(gancho, fg, (255, 255, 255, 255), 8, (10, 10, 20), shadow=(0, 10, acc + (255,), 0), gap=0.04))
    pb.alpha_composite(ti, ((1080 - ti.width) // 2, 330))
    pb.convert("RGB").save(os.path.join(ctx["out"], "portada-short.jpg"), quality=90)


# ================================================================== textos para YouTube
def nice(t):
    t = t.strip().lower()
    i = 1 if t[:1] in "¿¡" else 0
    return t[:i] + t[i:i + 1].upper() + t[i + 1:]


def creditos_txt(g, ctx, escenas):
    vistos, out = set(), []
    last = None
    for sc in escenas:
        spec = sc.get("imagen") or last
        last = spec
        _, c = ctx["img"](spec)
        if c and c["titulo"] not in vistos:
            vistos.add(c["titulo"])
            out.append(f"• {c['titulo'].replace('File:', '')} — {c['autor']} · {c['licencia']} · {c['pagina']}")
    return out


def fuentes_txt(g):
    out = []
    for f in g.get("fuentes", []):
        out.append(f"• {f['titulo']}: {f['url']}" if isinstance(f, dict) else f"• {f}")
    return out


def textos(g, ctx):
    out = ctx["out"]
    v = ctx.get("video") or ctx.get("_cache_tiempos", {}).get("video")
    tags = g.get("etiquetas", [])
    hashtags = " ".join(h if h.startswith("#") else "#" + h for h in g.get("hashtags", []))
    if v:
        caps = []
        for i, (s, sc) in enumerate(zip(v["starts"], g["escenas"])):
            cap = sc.get("capitulo")  # False: el rótulo se ve en pantalla pero no es capítulo
            txt = None if cap is False else (cap or (nice(sc["titulo"]) if sc.get("titulo") else None))
            st = 0 if i == 0 else s - 0.3
            if txt and (not caps or st - caps[-1][0] >= 10):
                caps.append([st, txt])
        if caps:
            caps[0][0] = 0
        cap_txt = "\n".join(f"{C.mmss(s)} {t}" for s, t in caps) if len(caps) >= 3 else ""
    else:
        cap_txt = ""
    S = g.get("short")
    if not g.get("escenas"):  # lote de solo Shorts
        return textos_short(g, ctx, S, hashtags, tags, None)
    partes = [g["titulo"], "", g.get("descripcion", "").strip()]
    if cap_txt:
        partes += ["", "📌 Capítulos", cap_txt]
    if g.get("fuentes"):
        partes += ["", "📚 Fuentes", *fuentes_txt(g)]
    mini = [{"imagen": g["miniatura_busqueda"]}] if g.get("miniatura_busqueda") else []  # la foto de la miniatura también lleva crédito
    cr = creditos_txt(g, ctx, g["escenas"] + mini)
    pie = ["", f"🔔 Suscríbete a {C.CANAL.title()}: una curiosidad nueva cada día.",
           "🎙️ Narración con voz sintética. Guion revisado con las fuentes de arriba.", "", hashtags]
    desc = "\n".join(partes + (["", "📷 Imágenes con licencia libre (Wikimedia Commons)", *cr] if cr else []) + pie).strip()
    fijado = os.path.join(out, "comentario-fijado.txt")
    if len(desc) > 4900:  # YouTube admite 5000 caracteres: los créditos completos van al comentario fijado
        open(fijado, "w", encoding="utf-8").write("\n".join(["📷 Créditos de las imágenes (Wikimedia Commons)", *cr]) + "\n")
        desc = "\n".join(partes + ["", f"📷 {len(cr)} fotos de Wikimedia Commons con licencia libre (CC BY, CC BY-SA, CC0 o dominio público). "
                                       "Autor, licencia y enlace de cada una en el comentario fijado."] + pie).strip()
        print(f"Créditos de las fotos en comentario-fijado.txt (la descripción pasaba de 5000 caracteres)")
    elif os.path.exists(fijado):
        os.remove(fijado)
    open(os.path.join(out, "descripcion.txt"), "w", encoding="utf-8").write(desc + "\n\nEtiquetas: " + ", ".join(tags) + "\n")

    if S:
        textos_short(g, ctx, S, hashtags, tags, g["titulo"])
    print("OK descripcion.txt")


def textos_short(g, ctx, S, hashtags, tags, largo):
    cr2 = creditos_txt(g, ctx, S["escenas"])
    ht = hashtags + (" #shorts" if "#shorts" not in hashtags.lower() else "")
    p2 = [S.get("titulo") or g.get("titulo"), "", S.get("descripcion", "").strip(), ""]
    p2 += [f"🎬 Vídeo completo en el canal: {largo}", ""] if largo else \
          [f"🔔 Suscríbete a {C.CANAL.title()}: una curiosidad nueva cada día.", ""]
    if g.get("fuentes"):
        p2 += ["📚 Fuentes", *fuentes_txt(g), ""]
    if cr2:
        p2 += ["📷 Imágenes", *cr2, ""]
    p2 += [ht]
    if not largo and tags:
        p2 += ["", "Etiquetas: " + ", ".join(tags)]
    open(os.path.join(ctx["out"], "descripcion-short.txt"), "w", encoding="utf-8").write("\n".join(p2).strip() + "\n")
    print("OK descripcion-short.txt")


# ================================================================== revisión
def fotogramas(gid, out):
    """Hoja con 8 fotogramas del vídeo y 4 del Short, para revisar el resultado de un vistazo."""
    sheet = Image.new("RGB", (1920, 2 * 300 + 520), (20, 20, 24))
    d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype(C.F_BOLD, 18)
    hay = False
    for name, n, (cw, ch), y0, cols in (("video.mp4", 8, (480, 270), 0, 4), ("short.mp4", 4, (270, 480), 600, 4)):
        p = os.path.join(out, name)
        if not os.path.exists(p):
            continue
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                   capture_output=True, text=True).stdout or 0)
        for k in range(n):
            t = dur * (k + 0.5) / n
            fp = os.path.join(C.trabajo(gid), f"fr_{k}.jpg")
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", p, "-frames:v", "1", fp], check=True)
            im = Image.open(fp).resize((cw - 6, ch - 6))
            x = (k % cols) * (1920 // cols) + (1920 // cols - cw) // 2
            y = y0 + (k // cols) * (ch + 30)
            sheet.paste(im, (x + 3, y + 3))
            d.text((x + 6, y + ch + 2), f"{name} {C.mmss(t)}", font=f, fill=(255, 255, 255))
            os.remove(fp)
            hay = True
    if hay:
        p = os.path.join(C.trabajo(gid), "fotogramas.jpg")
        sheet.save(p, quality=85)
        print(f"Fotogramas para revisar: {p}")


def historial(g):
    hp = os.path.join(C.ROOT, "historial.json")
    h = json.load(open(hp, encoding="utf-8")) if os.path.exists(hp) else []
    h = [x for x in h if x["id"] != g["_id"]]
    h.append({"fecha": g["_id"][:10], "id": g["_id"], "titulo": g.get("titulo") or g["short"]["titulo"],
              "tema": g.get("tema", ""), "formato": "video+short" if g.get("escenas") else "short"})
    h.sort(key=lambda x: x["id"])
    json.dump(h, open(hp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("guion")
    ap.add_argument("--solo", nargs="*", default=["video", "short", "miniatura", "textos"])
    a = ap.parse_args()
    g = C.cargar_guion(a.guion)
    out = C.salida(g["_id"])
    idir = C.trabajo(g["_id"], "img")
    cp = os.path.join(idir, "creditos.json")
    cred = json.load(open(cp, encoding="utf-8")) if os.path.exists(cp) else {}

    def img(spec):
        c = cred.get(spec) if spec and not spec.startswith("@") else None
        return (os.path.join(idir, c["archivo"]) if c else None), c

    faltan = [sc.get("imagen") for sc in g.get("escenas", []) + g.get("short", {}).get("escenas", [])
              if sc.get("imagen") and not sc["imagen"].startswith("@") and sc["imagen"] not in cred]
    if faltan:
        print(f"AVISO: {len(faltan)} imágenes sin descargar (se usará el fondo de la marca): {faltan[:5]}", file=sys.stderr)
    ctx = {"out": out, "img": img, "acc": C.hex2rgb(g.get("acento") or C.CFG["acento"]),
           "seed": int(hashlib.sha1(g["_id"].encode()).hexdigest()[:6], 16)}
    tp = os.path.join(C.trabajo(g["_id"]), "tiempos.json")
    if "video" in a.solo and g.get("escenas"):
        video(g, ctx)
    if "short" in a.solo and g.get("short"):
        short(g, ctx)
    if "miniatura" in a.solo:
        miniatura(g, ctx)
    if "video" in ctx:
        json.dump({"video": {"starts": ctx["video"]["starts"]}}, open(tp, "w"))
    elif os.path.exists(tp):
        ctx["_cache_tiempos"] = json.load(open(tp))
    if "textos" in a.solo:
        textos(g, ctx)
    fotogramas(g["_id"], out)
    historial(g)


if __name__ == "__main__":
    main()
