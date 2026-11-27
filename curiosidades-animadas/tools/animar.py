#!/usr/bin/env python3
"""DATOS CON CARA — motor de Shorts animados de curiosidades (vertical 1080x1920).

Cada guion (guiones/NN-slug.json) se convierte en un vídeo con personajes 2D que hablan,
fondos animados, rótulos, subtítulos, música y efectos de sonido. Todo generado aquí:
sin plantillas de terceros, sin música con derechos.

Comandos (desde la carpeta curiosidades-animadas/):
  python3 tools/animar.py lista               -> guiones disponibles
  python3 tools/animar.py render 01 [02 ...]  -> videos-listos/NN-slug.mp4 (+ .txt y portada)
  python3 tools/animar.py render todos
  python3 tools/animar.py guion 01            -> texto para pegar en ElevenLabs
  python3 tools/animar.py prueba 01 3         -> salida/prueba-01-3.png (fotograma de la escena 3)
  python3 tools/animar.py reparto             -> salida/reparto.png (todos los personajes)

Voz: por defecto, Piper (voz española, sin coste). Si dejas tu propio audio en
pon-aqui-tu-voz/NN.mp3 (o .wav / .m4a), se usa ese y se reparte entre las escenas.
Necesita: Python 3, numpy, Pillow, ffmpeg y piper-tts (con la voz en PIPER_VOICE).
"""
import json, math, os, random, re, subprocess, sys, wave, glob
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import personajes as PJ  # noqa: E402

FONTS = {
    "anton": os.path.join(ROOT, "tools", "fonts", "anton-latin-400-normal.woff"),
    "inter": os.path.join(ROOT, "tools", "fonts", "inter-latin-800-normal.woff"),
    "inter-reg": os.path.join(ROOT, "tools", "fonts", "inter-latin-400-normal.woff"),
}
PJ.FONTS = FONTS
GUIONES = os.path.join(ROOT, "guiones")
LISTOS = os.path.join(ROOT, "videos-listos")
SALIDA = os.path.join(ROOT, "salida")
TU_VOZ = os.path.join(ROOT, "pon-aqui-tu-voz")
CANAL = os.environ.get("CANAL", "Datos con Cara")
VOICE = os.environ.get("PIPER_VOICE", os.path.expanduser("~/.cache/piper-voces/es_ES-davefx-medium.onnx"))

W, H, FPS = 1080, 1920, 30
SR = 44100
INK = PJ.INK
YELLOW = (255, 214, 64)
PRE, POST = 0.10, 0.28          # margen antes/después de cada frase (s)
ROT_Y = 400                      # centro vertical de los rótulos
CAP_Y = 1410                     # centro vertical de los subtítulos

# Pronunciación para la voz (los subtítulos usan el texto original)
PRON = [(r"\bglamour\b", "glamur"), (r"\bOK\b", "oquei"), (r"\bYouTube\b", "Yutub"), (r"\bshorts?\b", "chorts")]


def pron(t):
    t = t.replace("*", "")
    for a, b in PRON:
        t = re.sub(a, b, t, flags=re.I)
    return t


def ease_out_back(p, s=1.70158):
    p = min(1.0, max(0.0, p)) - 1
    return p * p * ((s + 1) * p + s) + 1


def ease_out(p):
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


def ease_io(p):
    p = min(1.0, max(0.0, p))
    return 3 * p * p - 2 * p * p * p


def bounce(p):
    p = min(1.0, max(0.0, p))
    n, d = 7.5625, 2.75
    if p < 1 / d:
        return n * p * p
    if p < 2 / d:
        p -= 1.5 / d; return n * p * p + 0.75
    if p < 2.5 / d:
        p -= 2.25 / d; return n * p * p + 0.9375
    p -= 2.625 / d
    return n * p * p + 0.984375


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


_fonts = {}


def font(name, size):
    k = (name, size)
    if k not in _fonts:
        _fonts[k] = ImageFont.truetype(FONTS[name], size)
    return _fonts[k]


# =================================================================== sprites
_body, _state = {}, {}


def body(name, fase, texto, boca):
    fn, info = PJ.PERSONAJES[name]
    key = (name, fase, texto, boca if info.get("boca_propia") else 0)
    if key not in _body:
        L = PJ.Lienzo()
        fn(L, fase, texto, key[3])
        _body[key] = PJ.contorno(L.im, 5)
    return _body[key]


def sprite(name, size, fase=0, texto=None, expr="feliz", boca=0, parp=False, mira=(0, 0), gris=0.0):
    fn, info = PJ.PERSONAJES[name]
    if info.get("cara") is None:
        expr, boca, parp, mira = None, 0, False, (0, 0)
    gris = round(gris * 10) / 10
    key = (name, size, fase, texto, expr, boca, parp, mira, gris)
    im = _state.get(key)
    if im is None:
        im = body(name, fase, texto, boca).copy()
        if info.get("cara"):
            fx, fy, fs = info["cara"]
            PJ.cara(PJ.Lienzo(im), fx, fy, fs, expr, boca, parp, mira, info.get("piel", (255, 255, 255)),
                    sin_boca=info.get("boca_propia", False))
        im = im.resize((size, size), Image.LANCZOS)
        if gris > 0:   # desaturado (p. ej. el flamenco cuando nace gris)
            a = im.getchannel("A")
            rgb = im.convert("RGB")
            g = ImageOps.colorize(ImageOps.grayscale(rgb), (40, 34, 52), (238, 236, 240))
            im = Image.blend(rgb, g, gris)
            im.putalpha(a)
        if len(_state) > 900:
            _state.clear()
        _state[key] = im
    return im


# =================================================================== efectos visuales
_fx = {}


def fx_sprite(kind, size):
    key = (kind, size)
    if key in _fx:
        return _fx[key]
    L = PJ.Lienzo(n=200)
    if kind == "corazon":
        L.poly(PJ.heart_pts(100, 100, 5.2), (238, 64, 88), lw=7)
    elif kind == "brillo":
        pts = []
        for i in range(8):
            a = math.pi / 4 * i - math.pi / 2
            r = 90 if i % 2 == 0 else 26
            pts.append((100 + r * math.cos(a), 100 + r * math.sin(a)))
        L.poly(pts, (255, 240, 150), lw=6)
    elif kind in ("?", "!"):
        L.texto(100, 100, kind, 170, (255, 255, 255), stroke=9)
    elif kind == "sudor":
        L.poly(PJ.drop_pts(100, 120, 48, 30), (150, 214, 255), lw=7)
    elif kind == "zeta":
        L.texto(100, 100, "Z", 120, (255, 255, 255), stroke=8)
    im = L.im.resize((size, size), Image.LANCZOS)
    _fx[key] = im
    return im


def glow(color, size):
    key = ("glow", color, size)
    if key not in _fx:
        y, x = np.mgrid[0:size, 0:size].astype(np.float32)
        r = np.hypot(x - size / 2, y - size / 2) / (size / 2)
        a = np.clip(1 - r, 0, 1) ** 1.6 * 230
        arr = np.zeros((size, size, 4), np.uint8)
        arr[..., :3] = color
        arr[..., 3] = a.astype(np.uint8)
        _fx[key] = Image.fromarray(arr, "RGBA")
    return _fx[key]


_shadow = {}


def shadow(w):
    w = max(20, int(w) // 4 * 4)
    if w not in _shadow:
        h = max(8, w // 6)
        im = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
        ImageDraw.Draw(im).ellipse([20, 20, 20 + w, 20 + h], fill=(20, 10, 30, 70))
        _shadow[w] = im.filter(ImageFilter.GaussianBlur(8))
    return _shadow[w]


def paste(fr, im, cx, cy, alpha=1.0):
    if alpha <= 0.01:
        return
    if alpha < 0.99:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    fr.paste(im, (int(round(cx - im.width / 2)), int(round(cy - im.height / 2))), im)


# =================================================================== fondos
def vgrad(c0, c1, h=H, w=W):
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    g = np.array(c0, np.float32) * (1 - t) + np.array(c1, np.float32) * t
    return np.repeat(g, w, axis=1)


HW, HH = W // 2, H // 2
_yy, _xx = np.mgrid[0:HH, 0:HW].astype(np.float32)


class Fondo:
    """Fondo animado. frame(t) devuelve una imagen RGB de 1080x1920."""
    suelo = 1330

    def __init__(self, kind, color=None, seed=1):
        self.kind, self.seed = kind, seed
        rng = random.Random(seed)
        self.rng = rng
        k = kind
        if k == "rayos":
            c = hexrgb(color) if color else (255, 196, 61)
            self.c1 = np.array(c, np.float32)
            self.c2 = np.array(PJ.mix(c, (255, 255, 255), 0.28), np.float32)
            ang = np.arctan2(_yy - 470, _xx - 270)
            self.ang = ang
            r = np.hypot(_xx - 270, _yy - 470) / 900
            self.vig = (1 - 0.35 * np.clip(r, 0, 1) ** 1.5)[..., None]
        elif k == "lunares":
            c = hexrgb(color) if color else (120, 200, 255)
            self.c1 = np.array(c, np.float32)
            self.c2 = np.array(PJ.mix(c, (255, 255, 255), 0.22), np.float32)
        else:
            self.base = self._paisaje(k, rng)
            self.parts = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(6, 22), rng.uniform(0.6, 1.4), rng.uniform(0, 6.28))
                          for _ in range(26 if k == "mar" else 60)]

    def _paisaje(self, k, rng):
        S = self.suelo
        if k == "espacio":
            a = vgrad((18, 14, 52), (64, 26, 92))
            im = Image.fromarray(a.astype(np.uint8))
            neb = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            dn = ImageDraw.Draw(neb)
            for _ in range(7):
                x, y, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(180, 420)
                col = rng.choice([(120, 60, 200), (220, 80, 160), (60, 120, 220)])
                dn.ellipse([x - r, y - r * 0.6, x + r, y + r * 0.6], fill=col + (60,))
            neb = neb.filter(ImageFilter.GaussianBlur(90))
            im = Image.alpha_composite(im.convert("RGBA"), neb)
            d = ImageDraw.Draw(im)
            for _ in range(260):
                x, y, r = rng.uniform(0, W), rng.uniform(0, H), rng.choice([1, 1, 1.5, 2, 2.5])
                d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, rng.randint(120, 255)))
            for (x, y, r, col) in ((140, 1650, 90, (255, 140, 100)), (960, 560, 40, (140, 220, 255))):
                L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                ImageDraw.Draw(L).ellipse([x - r, y - r, x + r, y + r], fill=col + (200,), outline=INK + (200,), width=8)
                im = Image.alpha_composite(im, L)
            return im.convert("RGB")
        if k == "mar":
            a = vgrad((96, 214, 244), (14, 84, 150))
            im = Image.fromarray(a.astype(np.uint8)).convert("RGBA")
            rays = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            dr = ImageDraw.Draw(rays)
            for x in (120, 380, 640, 900):
                dr.polygon([(x - 40, 0), (x + 60, 0), (x + 260, H), (x - 60, H)], fill=(255, 255, 255, 36))
            rays = rays.filter(ImageFilter.GaussianBlur(30))
            im = Image.alpha_composite(im, rays)
            d = ImageDraw.Draw(im)
            for i, x in enumerate((70, 160, 930, 1010, 840)):
                h = 300 + (i * 97) % 220
                pts = [(x + 26 * math.sin(y / 60 + i), S + 60 - y) for y in range(0, h, 10)]
                d.line(pts, fill=INK, width=34, joint="curve")
                d.line(pts, fill=(64, 178, 96), width=20, joint="curve")
            sand = [(x, S + 20 + 18 * math.sin(x / 140)) for x in range(0, W + 41, 40)] + [(W, H), (0, H)]
            d.polygon(sand, fill=(246, 214, 150))
            d.line(sand[:-2], fill=INK, width=8, joint="curve")
            for _ in range(30):
                x, y = rng.uniform(0, W), rng.uniform(S + 70, H)
                d.ellipse([x - 6, y - 4, x + 6, y + 4], fill=(222, 186, 120))
            return im.convert("RGB")
        if k in ("desierto", "campo", "laguna"):
            if k == "desierto":
                sky = ((110, 200, 246), (210, 240, 255)); hills = [(242, 206, 140), (232, 184, 110)]
            elif k == "campo":
                sky = ((110, 200, 246), (214, 242, 255)); hills = [(132, 210, 110), (98, 186, 84)]
            else:
                sky = ((255, 168, 196), (255, 226, 160)); hills = [(214, 150, 190), (190, 120, 170)]
            a = vgrad(*sky)
            im = Image.fromarray(a.astype(np.uint8)).convert("RGBA")
            d = ImageDraw.Draw(im)
            sx, sy = (860, 330) if k != "laguna" else (540, 1030)
            sun = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(sun).ellipse([sx - 220, sy - 220, sx + 220, sy + 220], fill=(255, 250, 200, 90))
            sun = sun.filter(ImageFilter.GaussianBlur(50))
            im = Image.alpha_composite(im, sun)
            d = ImageDraw.Draw(im)
            d.ellipse([sx - 110, sy - 110, sx + 110, sy + 110], fill=(255, 236, 140) if k != "laguna" else (255, 200, 120),
                      outline=INK, width=8)
            if k == "desierto":
                for x, h in ((170, 260), (330, 170), (900, 210)):
                    y0 = S - 150
                    d.polygon([(x - h, y0), (x, y0 - h), (x + h, y0)], fill=(226, 190, 130), outline=INK)
                    d.line([(x - h, y0), (x, y0 - h), (x + h, y0)], fill=INK, width=6)
            base_y = S - 160 if k != "laguna" else 1080
            for i, col in enumerate(hills):
                y0 = base_y + i * 90
                pts = [(x, y0 + 50 * math.sin(x / 210 + i * 2.1) + 25 * math.sin(x / 90 + i)) for x in range(-20, W + 41, 20)]
                pts += [(W + 40, H), (-20, H)]
                d.polygon(pts, fill=col)
                d.line(pts[:-2], fill=INK, width=7, joint="curve")
            if k == "laguna":
                wa = vgrad((150, 214, 232), (70, 160, 200), h=H - 1150)
                im.paste(Image.fromarray(wa.astype(np.uint8)), (0, 1150))
                d = ImageDraw.Draw(im)
                d.line([(0, 1150), (W, 1150)], fill=INK, width=7)
                for x in (60, 120, 980, 1030):
                    d.line([(x, 1170), (x + 8, 1000)], fill=INK, width=14)
                    d.line([(x, 1170), (x + 8, 1000)], fill=(92, 150, 70), width=7)
                    d.ellipse([x - 4, 960, x + 20, 1030], fill=(140, 92, 56), outline=INK, width=5)
            else:
                g = (236, 200, 130) if k == "desierto" else (120, 200, 96)
                pts = [(x, S + 12 * math.sin(x / 130)) for x in range(-20, W + 41, 20)] + [(W + 40, H), (-20, H)]
                d.polygon(pts, fill=g)
                d.line(pts[:-2], fill=INK, width=8, joint="curve")
                if k == "campo":
                    for _ in range(26):
                        x, y = rng.uniform(20, W - 20), rng.uniform(S + 60, H - 40)
                        c = rng.choice([(255, 255, 255), (255, 214, 64), (255, 140, 170)])
                        for a in range(5):
                            aa = a * 1.2566
                            d.ellipse([x + 12 * math.cos(aa) - 8, y + 12 * math.sin(aa) - 8, x + 12 * math.cos(aa) + 8,
                                       y + 12 * math.sin(aa) + 8], fill=c, outline=INK, width=3)
                        d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(255, 180, 40))
            return im.convert("RGB")
        raise ValueError(f"fondo desconocido: {k}")

    def frame(self, t):
        k = self.kind
        if k == "rayos":
            v = np.sin(self.ang * 12 + t * 0.35)
            m = np.clip(v * 3 + 0.5, 0, 1)[..., None]
            a = (self.c1 * (1 - m) + self.c2 * m) * self.vig
            return Image.fromarray(a.astype(np.uint8)).resize((W, H), Image.BILINEAR)
        if k == "lunares":
            cell = 90
            u = (_xx + t * 22) % cell - cell / 2
            v = (_yy + t * 22) % cell - cell / 2
            off = ((np.floor((_yy + t * 22) / cell)) % 2) * cell / 2
            u = (_xx + t * 22 + off) % cell - cell / 2
            r = np.hypot(u, v)
            m = np.clip((18 - r) * 0.8, 0, 1)[..., None]
            a = self.c1 * (1 - m) + self.c2 * m
            return Image.fromarray(a.astype(np.uint8)).resize((W, H), Image.BILINEAR)
        fr = self.base.copy()
        d = ImageDraw.Draw(fr, "RGBA")
        if k == "mar":
            for x, y, r, sp, ph in self.parts:
                yy = (y - t * 90 * sp) % (self.suelo + 60) - 30
                xx = x + 14 * math.sin(t * 2 + ph)
                d.ellipse([xx - r, yy - r, xx + r, yy + r], outline=(255, 255, 255, 170), width=4)
                d.ellipse([xx - r * 0.4, yy - r * 0.6, xx - r * 0.05, yy - r * 0.25], fill=(255, 255, 255, 170))
        elif k == "espacio":
            for x, y, r, sp, ph in self.parts[:30]:
                a = 0.5 + 0.5 * math.sin(t * 3 * sp + ph)
                s = r * 0.5 * (0.5 + a)
                d.polygon([(x, y - s), (x + s * 0.25, y - s * 0.25), (x + s, y), (x + s * 0.25, y + s * 0.25), (x, y + s),
                           (x - s * 0.25, y + s * 0.25), (x - s, y), (x - s * 0.25, y - s * 0.25)], fill=(255, 255, 230, int(120 + 135 * a)))
        else:
            for i, (x, y, r, sp, ph) in enumerate(self.parts[:4]):
                cx = (x + t * 18 * sp) % (W + 400) - 200
                cy = 140 + (i * 173) % 520
                for dx, dy, rr in ((0, 0, 60), (60, -20, 70), (120, 0, 55), (60, 20, 60)):
                    d.ellipse([cx + dx - rr, cy + dy - rr * 0.7, cx + dx + rr, cy + dy + rr * 0.7], fill=(255, 255, 255, 235))
            if k == "laguna":
                for i in range(8):
                    y = 1200 + i * 90
                    x0 = (i * 211 + t * 40 * (1 + i % 3)) % (W + 300) - 150
                    d.line([(x0, y), (x0 + 120, y)], fill=(255, 255, 255, 150), width=6)
        return fr


# =================================================================== textos
def rich_tokens(text):
    """'hola *mundo*.' -> [('hola', False, False), ('mundo', True, False), ('.', False, True)]
    El tercer valor indica que va pegado a la palabra anterior (sin espacio)."""
    out, hl = [], False
    glue_next = False
    for part in re.split(r"(\*)", text):
        if part == "*":
            hl = not hl
            continue
        if not part:
            continue
        words = part.split()
        for i, w in enumerate(words):
            glue = i == 0 and bool(out) and not part[0].isspace() and glue_next
            out.append((w, hl, glue))
        glue_next = not part[-1].isspace()
    return out


def _tw(f, ln):
    return sum(f.getlength(w) + (0 if g or i == 0 else f.getlength(" ")) for i, (w, _, g) in enumerate(ln))


def text_img(lines, fname, size, maxw, stroke, color=(255, 255, 255), hl=YELLOW, shadow_off=0, spacing=1.05):
    while True:
        f = font(fname, size)
        widths = [_tw(f, ln) for ln in lines]
        if max(widths) <= maxw or size < 30:
            break
        size -= 4
    lh = int(size * spacing)
    pad = stroke + 10 + shadow_off
    w_ = int(max(widths)) + pad * 2
    h_ = lh * len(lines) + pad * 2 + int(size * 0.25)
    im = Image.new("RGBA", (w_, h_), INK + (0,))
    d = ImageDraw.Draw(im)
    for li, (ln, wd) in enumerate(zip(lines, widths)):
        y = pad + li * lh
        for layer in ("shadow", "text"):
            if layer == "shadow" and not shadow_off:
                continue
            x = (w_ - wd) / 2
            for i, (w, h, g) in enumerate(ln):
                if i and not g:
                    x += f.getlength(" ")
                off = shadow_off if layer == "shadow" else 0
                fill = INK if layer == "shadow" else (hl if h else color)
                d.text((x, y + off), w, font=f, fill=fill, stroke_width=stroke, stroke_fill=INK)
                x += f.getlength(w)
    return im


def rotulo_img(text, color=None):
    toks = rich_tokens(text.upper().replace("|", " | "))
    lines, cur = [], []
    for w, h, g in toks:
        if w == "|":
            lines.append(cur); cur = []
            continue
        cur.append((w, h, g))
    if cur:
        lines.append(cur)
    if len(lines) == 1 and sum(len(t[0]) for t in lines[0]) > 15 and len(lines[0]) > 1:
        ws = lines[0]
        cuts = [i for i in range(1, len(ws)) if not ws[i][2]]
        if cuts:
            best = min(cuts, key=lambda i: abs(sum(len(t[0]) for t in ws[:i]) - sum(len(t[0]) for t in ws[i:])))
            lines = [ws[:best], ws[best:]]
    col = hexrgb(color) if color else (255, 255, 255)
    return text_img(lines, "anton", 150, 940, 12, color=col, shadow_off=12, spacing=1.14)


def caption_chunks(text):
    toks = rich_tokens(text)
    out, cur = [], []
    for j, (w, h, g) in enumerate(toks):
        if g and not cur and out:          # la puntuación se queda con su palabra
            out[-1].append((w, h, g))
            continue
        cur.append((w, h, g))
        n = sum(len(t[0]) for t in cur)
        nxt_glued = j + 1 < len(toks) and toks[j + 1][2]
        if not nxt_glued and (sum(1 for t in cur if not t[2]) >= 3 or n >= 14 or w[-1] in ".,?!:;…"):
            out.append(cur); cur = []
    if cur:
        if out and len(cur) == 1 and sum(len(t[0]) for t in out[-1]) + len(cur[0][0]) < 18:
            out[-1] += cur
        else:
            out.append(cur)
    return out


# =================================================================== audio
def read_wav(path):
    with wave.open(path) as w:
        sr, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
        a = np.frombuffer(w.readframes(n), np.int16).astype(np.float32) / 32768
    if ch > 1:
        a = a.reshape(-1, ch).mean(1)
    return a, sr


def to_mono44(path, out, pitch=1.0):
    af = ["aresample=44100"]
    if abs(pitch - 1) > 0.01:
        af = [f"rubberband=pitch={pitch:.3f}:formant=preserved"] if pitch < 1 else [f"rubberband=pitch={pitch:.3f}"]
        af.append("aresample=44100")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", path, "-af", ",".join(af), "-ac", "1", "-ar", "44100", out], check=True)
    return read_wav(out)[0]


def tts(text, path, length=0.92):
    if not os.path.exists(path):
        if not os.path.exists(VOICE):
            sys.exit(f"No encuentro la voz de Piper en {VOICE}. Indica la ruta con PIPER_VOICE=... o pon tu audio en pon-aqui-tu-voz/.")
        subprocess.run([sys.executable, "-m", "piper", "-m", VOICE, "-f", path, "--length-scale", str(length),
                        "--sentence-silence", "0.12"], input=pron(text).encode(), check=True, capture_output=True)


def trim(a, thr=0.012):
    idx = np.where(np.abs(a) > thr)[0]
    if len(idx) == 0:
        return a
    return a[max(0, idx[0] - 600): idx[-1] + 1500]


def tone(f, dur, decay=6.0, harm=((1, 1.0),), attack=0.004):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = sum(a * np.sin(2 * np.pi * f * m * t) for m, a in harm)
    env = np.exp(-t * decay) * np.minimum(1, t / attack)
    return (y * env).astype(np.float32)


def noise(dur, seed=0):
    return np.random.default_rng(seed).standard_normal(int(dur * SR)).astype(np.float32)


def bandpass(x, lo, hi):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, len(x)).astype(np.float32)


def sweep(f0, f1, dur, decay=0, vib=0, vibf=6, harm=((1, 1),)):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f0 * (f1 / f0) ** (t / dur) * (1 + vib * np.sin(2 * np.pi * vibf * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = sum(a * np.sin(m * ph) for m, a in harm)
    env = np.sin(np.pi * np.minimum(1, t / dur)) ** 0.5 if not decay else np.exp(-t * decay) * np.minimum(1, t / 0.004)
    return (y * env).astype(np.float32)


_sfx = {}


def addat(y, s, w, g=1.0):
    """Suma la onda w dentro de y a partir de la muestra s (recortando lo que sobre)."""
    if s >= len(y):
        return
    w = w[: len(y) - s]
    y[s:s + len(w)] += w * g


def sfx(name):
    if name in _sfx:
        return _sfx[name]
    if name == "pop":
        y = sweep(950, 260, 0.09, decay=40) * 0.9
    elif name == "pop2":
        y = sweep(1600, 600, 0.07, decay=50) * 0.6
    elif name == "whoosh":
        n = noise(0.42, 3)
        t = np.arange(len(n)) / SR
        env = (np.minimum(1, t / 0.16) * np.exp(-np.maximum(0, t - 0.16) * 9)) ** 1.5
        y = bandpass(n, 350, 2800) * env * 0.5
    elif name == "boing":
        t = np.arange(int(0.55 * SR)) / SR
        f = 210 * (1 + 0.45 * np.exp(-t * 5) * np.sin(2 * np.pi * 11 * t)) * (1 + 0.3 * t)
        y = (np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.25 * np.sin(4 * np.pi * np.cumsum(f) / SR)) * np.exp(-t * 4.5) * 0.7
    elif name == "ding":
        y = tone(1568, 1.1, 3.5, ((1, 1), (2.0, 0.4), (2.76, 0.25), (5.4, 0.1))) * 0.45
    elif name == "brillo":
        y = np.zeros(int(0.7 * SR), np.float32)
        for i, f in enumerate((1047, 1319, 1568, 2093)):
            s = int(i * 0.06 * SR)
            n_ = tone(f, 0.7 - i * 0.06, 6, ((1, 1), (2.76, 0.2)))
            addat(y, s, n_, 0.3)
    elif name == "tada":
        y = np.zeros(int(1.3 * SR), np.float32)
        for s0, d0 in ((0, 0.16), (0.18, 1.1)):
            for f in (523, 659, 784, 1047):
                n_ = tone(f, d0, 2.5 if d0 > 0.5 else 9, tuple((m, 1 / m) for m in range(1, 7)), attack=0.01)
                s = int(s0 * SR)
                addat(y, s, n_, 0.12)
    elif name in ("subida", "giro"):
        y = sweep(420, 1500, 0.5, vib=0.03) * 0.35
    elif name == "bajada":
        y = sweep(1400, 380, 0.55, vib=0.03) * 0.35
    elif name == "brr":
        t = np.arange(int(0.45 * SR)) / SR
        y = np.sign(np.sin(2 * np.pi * 95 * t)) * (0.5 + 0.5 * np.sin(2 * np.pi * 22 * t)) * np.exp(-t * 3) * 0.18
        y = bandpass(y.astype(np.float32), 60, 1800)
    elif name == "latido":
        y = np.zeros(int(0.5 * SR), np.float32)
        for s0, a in ((0, 1), (0.17, 0.75)):
            k = sweep(110, 45, 0.18, decay=14) * a
            s = int(s0 * SR)
            addat(y, s, k)
        y *= 0.9
    elif name == "gota":
        y = sweep(500, 1700, 0.07, decay=35) * 0.55
    elif name == "golpe":
        k = sweep(140, 40, 0.25, decay=12)
        n = bandpass(noise(0.25, 5), 200, 3000) * np.exp(-np.arange(int(0.25 * SR)) / SR * 30) * 0.4
        y = (k + n[:len(k)]) * 0.8
    elif name == "badumtss":   # redoble de chiste: ba-dum-tss
        y = np.zeros(int(1.4 * SR), np.float32)
        for s0, f0 in ((0.0, 190), (0.14, 150)):
            tom = sweep(f0, f0 * 0.75, 0.2, decay=16) * 0.8
            sn = bandpass(noise(0.14, int(f0)), 400, 5000) * np.exp(-np.arange(int(0.14 * SR)) / SR * 30) * 0.35
            addat(y, int(s0 * SR), tom)
            addat(y, int(s0 * SR), sn)
        crash = bandpass(noise(1.1, 21), 3500, 15000) * np.exp(-np.arange(int(1.1 * SR)) / SR * 4.5)
        addat(y, int(0.3 * SR), sweep(120, 45, 0.25, decay=14), 0.9)
        addat(y, int(0.3 * SR), crash, 0.55)
        y = y / (np.abs(y).max() + 1e-9) * 0.8
    elif name in ("risa", "trompeta"):   # trompetilla triste (wah-wah-wah-waaah)
        y = np.zeros(int(1.6 * SR), np.float32)
        for i, f in enumerate((392, 370, 349, 330)):
            d0 = 0.32 if i < 3 else 0.7
            n_ = sweep(f, f * 0.97, d0, vib=0.02 if i < 3 else 0.04, vibf=5, harm=tuple((m, 1 / m) for m in range(1, 8)))
            s = int(i * 0.34 * SR)
            addat(y, s, n_, 0.16)
    else:
        raise ValueError(f"sonido desconocido: {name}")
    _sfx[name] = y.astype(np.float32)
    return _sfx[name]


def musica(dur, seed):
    rng = random.Random(seed)
    bpm = rng.choice([112, 116, 120, 124])
    beat = 60 / bpm
    e = beat / 2
    root = 48 + rng.choice([0, 2, 5, 7])
    progs = [[(0, 4, 7), (9, 12, 16), (5, 9, 12), (7, 11, 14)],
             [(0, 4, 7), (5, 9, 12), (7, 11, 14), (5, 9, 12)],
             [(0, 4, 7), (7, 11, 14), (9, 12, 16), (5, 9, 12)]]
    prog = rng.choice(progs)
    penta = [0, 2, 4, 7, 9]
    scale = [p + 12 * o for o in (1, 2) for p in penta] + [24 + 12]
    n = int((dur + 2) * SR)
    out = np.zeros(n, np.float32)
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)

    def add(t0, w, g=1.0):
        s = int(t0 * SR)
        if s >= n:
            return
        w = w[: n - s]
        out[s:s + len(w)] += w * g

    rhythms = [[1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 0], [1, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1, 1, 0, 1, 0, 0],
               [1, 0, 0, 1, 1, 0, 1, 1, 1, 0, 0, 1, 1, 0, 1, 0]]
    rhythm = rng.choice(rhythms)
    idx = 4
    motif = []
    for on in rhythm:
        if on:
            idx = max(0, min(len(scale) - 1, idx + rng.choice([-2, -1, -1, 1, 1, 2, 0])))
            motif.append(idx)
        else:
            motif.append(None)
    bars = int(dur / (beat * 4)) + 2
    hat_noise = bandpass(noise(0.05, 9), 6000, 16000)
    clap_noise = bandpass(noise(0.12, 11), 900, 5000)
    for b in range(bars):
        ch = prog[b % 4]
        t0 = b * beat * 4
        # bajo pizzicato
        for k, deg in ((0, ch[0]), (2, ch[0]), (3, ch[2] - 12)):
            add(t0 + k * beat, tone(hz(root - 12 + deg), beat * 0.9, 7, ((1, 1), (2, 0.45), (3, 0.15))), 0.33)
        # acordes de marimba a contratiempo
        for k in range(4):
            for deg in ch:
                add(t0 + k * beat + e, tone(hz(root + 12 + deg), 0.25, 16, ((1, 1), (4, 0.25))), 0.06)
        # percusión
        for k in range(8):
            add(t0 + k * e + (0.012 if k % 2 else 0), hat_noise * np.exp(-np.arange(len(hat_noise)) / SR * 70), 0.06 if k % 2 else 0.1)
        for k in (0, 2):
            add(t0 + k * beat, sweep(120, 45, 0.2, decay=16), 0.45)
        for k in (1, 3):
            add(t0 + k * beat, clap_noise * np.exp(-np.arange(len(clap_noise)) / SR * 28), 0.18)
        # melodía (frase de 2 compases que se repite con variaciones)
        if b % 8 in (6, 7) and b > 0:
            continue
        half = (b % 2) * 8
        for i in range(8):
            m = motif[half + i]
            if m is None:
                continue
            if b % 4 >= 2 and i >= 5:
                m = max(0, min(len(scale) - 1, m + (1 if b % 4 == 2 else -1)))
            note = root + 12 + scale[m]
            if i in (0, 4):
                note = min((root + 12 + 12 + c for c in ch + tuple(c + 12 for c in ch)), key=lambda x: abs(x - note))
            add(t0 + i * e, tone(hz(note), e * 1.6, 7, ((1, 1), (2, 0.35), (3, 0.12), (4.2, 0.06))), 0.2)
    y = out[: int(dur * SR)]
    k = np.exp(-np.arange(48) / 5.0); k /= k.sum()
    y = np.convolve(y, k, mode="same")
    fade = int(0.8 * SR)
    y[-fade:] *= np.linspace(1, 0, fade)
    return (y / (np.abs(y).max() + 1e-9) * 0.8).astype(np.float32)


def media_movil(x, k):
    """Media móvil centrada de k muestras (rápida, con sumas acumuladas)."""
    k = max(1, int(k))
    c = np.cumsum(np.concatenate([np.zeros(k // 2 + 1), x, np.zeros(k - k // 2)]).astype(np.float64))
    return ((c[k:k + len(x)] - c[:len(x)]) / k).astype(np.float32)


def env_frames(a, t0, dur):
    """Volumen de la voz por fotograma (0..1) para mover la boca."""
    nf = int(math.ceil(dur * FPS)) + 2
    out = np.zeros(nf, np.float32)
    hop = SR // FPS
    for i in range(nf):
        s = int((i / FPS - t0) * SR)
        if s < 0 or s >= len(a):
            continue
        out[i] = np.sqrt(np.mean(a[s:s + hop] ** 2) + 1e-12)
    p = np.percentile(out[out > 0], 92) if np.any(out > 0) else 1
    return np.clip(out / (p + 1e-9), 0, 1.2)


def split_user_voice(a, texts, ref=None):
    """Reparte un audio completo entre las escenas, cortando en silencios.
    ref = duración de referencia de cada frase (la de Piper); si no hay, se estima por el texto."""
    hop = int(0.01 * SR)
    rms = np.array([np.sqrt(np.mean(a[i:i + hop] ** 2)) for i in range(0, len(a) - hop, hop)])
    thr = max(0.01, np.percentile(rms, 90) * 0.08)
    voiced = rms > thr
    if not voiced.any():
        sys.exit("El audio de pon-aqui-tu-voz está en silencio.")
    first, last = np.argmax(voiced), len(voiced) - np.argmax(voiced[::-1])
    sil = []
    i = first
    while i < last:
        if not voiced[i]:
            j = i
            while j < last and not voiced[j]:
                j += 1
            if j - i >= 12:
                sil.append(((i + j) / 2, j - i))
            i = j
        else:
            i += 1
    # elige a la vez los cortes (entre los silencios) que mejor encajan con la longitud de cada frase,
    # dando preferencia a las pausas largas
    n = len(texts)
    def peso(t):   # letras + pausas internas por puntuación
        t = pron(t).strip()
        core = t.rstrip(".?!…¡¿ ")
        return len(t) + 14 * len(re.findall(r"\.\.\.|…|[.?!]", core)) + 5 * core.count(",") + 5 * core.count(":")
    L = np.array(ref if ref is not None else [peso(t) for t in texts], float)
    exp = (last - first) * L / L.sum()
    if len(sil) < n - 1:
        cum = np.cumsum(L)[:-1] / L.sum()
        cuts = [first + c * (last - first) for c in cum]
    else:
        pts = [(first, 0)] + sil + [(last, 0)]
        m = len(pts)
        INF = float("inf")
        cost = [[INF] * m for _ in range(n + 1)]
        back = [[-1] * m for _ in range(n + 1)]
        cost[0][0] = 0.0
        for k in range(1, n + 1):
            js = [m - 1] if k == n else range(1, m - 1)
            for j in js:
                for i in range(j):
                    if cost[k - 1][i] == INF:
                        continue
                    d = pts[j][0] - pts[i][0]
                    c = cost[k - 1][i] + ((d - exp[k - 1]) / exp[k - 1]) ** 2 - (0.25 * min(pts[j][1], 60) / 60 if k < n else 0)
                    if c < cost[k][j]:
                        cost[k][j], back[k][j] = c, i
        cuts, j = [], m - 1
        for k in range(n, 1, -1):
            j = back[k][j]
            cuts.append(pts[j][0])
        cuts = cuts[::-1]
    bounds = [first] + cuts + [last]
    return [a[int(bounds[i] * hop): int(bounds[i + 1] * hop)] for i in range(len(texts))]


# =================================================================== guion -> línea de tiempo
def load(vid):
    files = sorted(glob.glob(os.path.join(GUIONES, f"{vid}-*.json")))
    if not files:
        sys.exit(f"No hay guion {vid} en guiones/")
    v = json.load(open(files[0]))
    v["_file"] = files[0]
    return v


def when(val, T, default=0.0):
    """Segundos desde el inicio de la escena. Acepta números (s) o "60%" (punto de la frase)."""
    if val is None:
        return default
    if isinstance(val, str) and val.strip().endswith("%"):
        return T["vstart"] - T["start"] + T["vdur"] * float(val.strip()[:-1]) / 100
    if val == "fin":
        return T["vstart"] - T["start"] + T["vdur"] + 0.05
    return float(val)


def prop_of(key):
    return key.split("#")[0]


def build_timeline(v, tmp):
    scenes = v["escenas"]
    user = None
    for ext in ("mp3", "wav", "m4a", "ogg"):
        p = os.path.join(TU_VOZ, f"{v['id']}.{ext}")
        if os.path.exists(p):
            user = to_mono44(p, os.path.join(tmp, "tu-voz.wav"))
            break
    if user is not None:
        ref = None
        if os.path.exists(VOICE):   # duración de cada frase leída por Piper, como referencia para repartir
            ref = []
            for i, sc in enumerate(scenes):
                raw = os.path.join(tmp, f"ref{i:02d}.wav")
                tts(sc["texto"], raw, 1.0)
                ref.append(len(trim(read_wav(raw)[0])))
        parts = [trim(p) for p in split_user_voice(user, [s["texto"] for s in scenes], ref)]
        print(f"  usando tu voz: pon-aqui-tu-voz/{v['id']}.*")
    else:
        parts = []
        for i, sc in enumerate(scenes):
            spk = sc.get("habla")
            info = PJ.PERSONAJES.get(prop_of(spk), (None, {}))[1] if spk else {}
            pitch = sc.get("tono", info.get("voz", 1.0))
            raw = os.path.join(tmp, f"v{i:02d}.wav")
            tts(sc["texto"], raw, sc.get("velocidad", 1.0 if not info.get("rapido") else 0.94))
            parts.append(trim(to_mono44(raw, os.path.join(tmp, f"v{i:02d}-44.wav"), pitch)))
    t = 0.0
    tl = []
    for i, (sc, a) in enumerate(zip(scenes, parts)):
        pre = PRE if i else 0.18
        d = len(a) / SR
        end = t + pre + d + POST + sc.get("pausa", 0)
        tl.append(dict(start=t, vstart=t + pre, vdur=d, end=end, audio=a))
        t = end
    tl[-1]["end"] += 0.5
    return tl


# =================================================================== render
class Actor:
    pass


def scene_actors(v, si, tl):
    sc = v["escenas"][si]
    st = tl[si]["start"]
    out = {}
    for key, a in sc.get("actores", {}).items():
        A = Actor()
        A.key, A.prop = key, prop_of(key)
        if A.prop not in PJ.PERSONAJES:
            sys.exit(f"Personaje desconocido '{A.prop}' en escena {si + 1}. Disponibles: {', '.join(PJ.PERSONAJES)}")
        A.info = PJ.PERSONAJES[A.prop][1]
        A.x, A.y = a.get("x", 0.5) * W, a.get("y", 0.5) * H
        A.s = a.get("s", 1.0)
        A.expr = a.get("cara", "feliz")
        A.t0 = st + when(a.get("retraso"), tl[si])
        A.entra = a.get("entra", "pop")
        A.accion = a.get("accion")
        A.accion_t = (st + when(a["accion_en"], tl[si])) if isinstance(a.get("accion_en"), str) else A.t0 + a.get("accion_en", 0.45)
        A.mira = a.get("mira")
        A.espejo = a.get("espejo", False)
        A.texto = a.get("texto")
        A.z = a.get("z", 0)
        A.gris = a.get("gris", 0.0)
        A.gris_t = st + when(a.get("gris_en"), tl[si])
        A.seed = sum(map(ord, key))
        out[key] = A
    return out


MIRA = {"izq": (-1, 0), "der": (1, 0), "arriba": (0, -1), "abajo": (0, 1), "centro": (0, 0)}


def render(vid, only_frame=None):
    v = load(vid)
    name = os.path.splitext(os.path.basename(v["_file"]))[0]
    tmp = os.path.join(ROOT, "_tmp", name)
    os.makedirs(tmp, exist_ok=True)
    os.makedirs(LISTOS, exist_ok=True)
    tl = build_timeline(v, tmp)
    total = tl[-1]["end"]
    scenes = v["escenas"]
    nS = len(scenes)
    seed = int(v["id"]) if v["id"].isdigit() else 7

    # ---- actores, fondos, rótulos y subtítulos por escena
    acts = [scene_actors(v, i, tl) for i in range(nS)]
    fondos, fkeys = {}, []
    for i, sc in enumerate(scenes):
        fk = (sc.get("fondo", v.get("fondo", "rayos")), sc.get("color", v.get("color")))
        fkeys.append(fk)
        if fk not in fondos:
            fondos[fk] = Fondo(fk[0], fk[1], seed + len(fondos))
    whip = [i > 0 and (fkeys[i] != fkeys[i - 1] or scenes[i].get("corte")) for i in range(nS)]
    rots = []
    for i, sc in enumerate(scenes):
        r = sc.get("rotulo")
        rots.append(rotulo_img(r, sc.get("rotulo_color")) if r else None)
    rot_t0 = []
    for i, sc in enumerate(scenes):
        same = i > 0 and sc.get("rotulo") and sc.get("rotulo") == scenes[i - 1].get("rotulo") and not whip[i]
        rot_t0.append(rot_t0[-1] if same else tl[i]["start"] + when(sc.get("rotulo_en"), tl[i], 0.08))
    caps = []
    for i, sc in enumerate(scenes):
        T = tl[i]
        ch = caption_chunks(sc["texto"])
        Ls = [sum(len(t[0]) for t in c) + 2 for c in ch]
        c0 = T["vstart"]
        for c, l in zip(ch, Ls):
            cd = T["vdur"] * l / sum(Ls)
            caps.append((c0, c0 + cd, text_img([c], "inter", 82, 920, 11)))
            c0 += cd
    envs = [env_frames(T["audio"], T["vstart"] - T["start"], T["end"] - T["start"]) for T in tl]

    # ---- sonido: voz + música + efectos
    if only_frame is None:
        n = int(total * SR) + SR
        voice = np.zeros(n, np.float32)
        fx = np.zeros(n, np.float32)
        for T in tl:
            s = int(T["vstart"] * SR)
            a = T["audio"] / (np.abs(T["audio"]).max() + 1e-9) * 0.9
            voice[s:s + len(a)] += a

        def ev(t, name, g=1.0):
            y = sfx(name)
            s = int(max(0, t) * SR)
            fx[s:s + len(y)] += y[: n - s] * g

        for i, sc in enumerate(scenes):
            st = tl[i]["start"]
            if whip[i]:
                ev(st - 0.12, "whoosh", 0.8)
            prev = acts[i - 1] if i else {}
            for k, A in acts[i].items():
                if k in prev and not whip[i]:
                    continue
                if A.entra == "pop":
                    ev(A.t0, "pop", 0.7)
                elif A.entra in ("izq", "der"):
                    ev(A.t0, "whoosh", 0.6)
                elif A.entra == "cae":
                    ev(A.t0 + 0.32, "boing", 0.6)
                if A.accion:
                    ev(A.accion_t, {"girar": "giro", "saltar": "boing", "temblar": "brr", "crecer": "subida",
                                    "latir": "latido", "encoger": "bajada"}.get(A.accion, "pop"), 0.7)
            if rots[i] is not None and rot_t0[i] >= st:
                ev(rot_t0[i], "pop2", 0.6)
            for f in sc.get("fx", []):
                snd = {"corazones": "ding", "brillos": "brillo", "interrogacion": "pop2", "exclamacion": "golpe",
                       "sudor": "gota", "confeti": "tada", "zzz": None, "resplandor": "brillo"}.get(f.get("tipo"))
                if snd:
                    ev(st + when(f.get("retraso"), tl[i], 0.2), snd, 0.55)
            for s_ in sc.get("sfx", []):
                nm, off = (s_, 0.0) if isinstance(s_, str) else (s_[0], s_[1])
                ev(st + when(off, tl[i]), nm, 0.7)
        mus = musica(total + 0.5, seed)[:n]
        mus = np.pad(mus, (0, n - len(mus)))
        e = media_movil(np.abs(voice), 0.08 * SR)
        duck = media_movil(1 - 0.6 * np.clip(e * 10, 0, 1), 0.25 * SR)
        mix_ = voice + mus * 0.30 * duck + fx * 0.55
        mix_ = np.tanh(mix_ * 1.1) / 1.1
        mix_ = mix_[: int(total * SR)]
        wav = os.path.join(tmp, "mezcla.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((np.clip(mix_, -1, 1) * 32767).astype(np.int16).tobytes())

    # ---- fotogramas
    def scene_at(t):
        for i, T in enumerate(tl):
            if t < T["end"]:
                return i
        return nS - 1

    blinks = {}

    def is_blink(key, t):
        if key not in blinks:
            r = random.Random(sum(map(ord, key)) * 7 + seed)
            bl, x = [], r.uniform(0.6, 2.0)
            while x < total + 5:
                bl.append(x); x += r.uniform(1.8, 4.2)
            blinks[key] = bl
        return any(0 <= t - b < 0.13 for b in blinks[key])

    def actor_state(A, si, t, prev):
        """Posición, escala, deformación y giro del actor en el instante t."""
        lt = t - A.t0
        x, y, s = A.x, A.y, A.s
        alpha = 1.0
        if lt < 0:
            return None
        P = prev.get(A.key) if prev else None
        gris = A.gris
        if P is not None and not whip[si]:
            p = ease_io(lt / 0.4)
            x, y, s = P.x + (A.x - P.x) * p, P.y + (A.y - P.y) * p, P.s + (A.s - P.s) * p
            gris = P.gris + (A.gris - P.gris) * ease_io((t - A.gris_t) / 0.5)
        elif A.entra == "pop":
            s = A.s * ease_out_back(lt / 0.36, 2.2)
        elif A.entra in ("izq", "der"):
            p = ease_out_back(lt / 0.45, 1.2)
            x0 = -0.35 * W if A.entra == "izq" else 1.35 * W
            x = x0 + (A.x - x0) * p
        elif A.entra == "cae":
            y = -0.3 * H + (A.y + 0.3 * H) * bounce(lt / 0.6)
        elif A.entra == "aparece":
            alpha = min(1, lt / 0.3)
        sx = sy = 1.0
        rot = 0.0
        ph = A.seed % 10
        if A.info.get("suelo"):
            b = math.sin((t + ph) * 2 * math.pi * 0.7)
            sy += 0.022 * b; sx -= 0.016 * b
        else:
            y += 14 * math.sin((t + ph) * 2 * math.pi * 0.45)
            rot += 2.5 * math.sin((t + ph) * 2 * math.pi * 0.3)
        at = t - A.accion_t
        if A.accion and at >= 0:
            if A.accion == "girar" and at < 0.7:
                rot += 360 * ease_io(at / 0.7)
            elif A.accion == "saltar":
                for j in range(2):
                    q = (at - j * 0.42) / 0.42
                    if 0 <= q < 1:
                        y -= 120 * 4 * q * (1 - q)
                        sy += 0.08 * math.sin(q * math.pi); sx -= 0.05 * math.sin(q * math.pi)
            elif A.accion == "temblar":
                x += 9 * math.sin(t * 70); rot += 2 * math.sin(t * 55)
            elif A.accion == "latir":
                k_ = abs(math.sin(at * math.pi * 2.2)) ** 3
                sx += 0.1 * k_; sy += 0.1 * k_
            elif A.accion == "crecer":
                g = 1 + 0.3 * ease_out_back(at / 0.5)
                sx *= g; sy *= g
            elif A.accion == "encoger":
                g = 1 - 0.35 * ease_out(at / 0.5)
                sx *= g; sy *= g
        return x, y, s, sx, sy, rot, alpha, gris

    def draw_actor(fr, A, si, t, prev, speaker, spk_pos, env_v):
        st = actor_state(A, si, t, prev)
        if st is None:
            return
        x, y, s, sx, sy, rot, alpha, gris = st
        if s <= 0.02:
            return
        talking = (A.key == speaker) and env_v > 0.04
        boca = 0
        if A.key == speaker:
            boca = 0 if env_v < 0.2 else (1 if env_v < 0.55 else 2)
            sy += 0.05 * min(1, env_v); sx -= 0.03 * min(1, env_v)
        if A.mira:
            mira = MIRA.get(A.mira, (0, 0))
        elif speaker and A.key != speaker and spk_pos is not None:
            mira = (1 if spk_pos[0] > x else -1, 0)
        else:
            mira = (0, 0)
        if A.espejo:
            mira = (-mira[0], mira[1])
        fases = A.info.get("fases", 1)
        fase = int(t * (14 if A.info.get("rapido") else 5)) % fases if fases > 1 else 0
        size = max(8, int(600 * s))
        im = sprite(A.prop, size, fase, A.texto, A.expr, boca, is_blink(A.key, t) and not talking, mira, gris)
        if A.espejo:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        w2, h2 = max(4, int(im.width * sx)), max(4, int(im.height * sy))
        if (w2, h2) != im.size:
            im = im.resize((w2, h2), Image.BILINEAR)
        cy = y
        if A.info.get("suelo"):
            cy = y - (h2 - size) / 2    # deforma desde los pies
            sh = shadow(size * 0.62)
            paste(fr, sh, x, y + size * (A.info.get("pie", 560) - 300) / 600 - 4, alpha)
        if abs(rot) > 0.3:
            im = im.rotate(-rot, Image.BICUBIC, expand=True)
        paste(fr, im, x, cy, alpha)
        return x, cy, size

    def fx_layer(fr, sc, si, t, pos, front=True):
        st = tl[si]["start"]
        for fi, f in enumerate(sc.get("fx", [])):
            kind = f.get("tipo")
            t0 = st + when(f.get("retraso"), tl[si], 0.2)
            lt = t - t0
            if lt < 0:
                continue
            tgt = f.get("en")
            if tgt and tgt in pos:
                ax, ay, asz = pos[tgt]
            else:
                ax, ay, asz = W / 2, H * 0.45, 500
            r = random.Random(fi * 31 + si)
            if kind == "resplandor" and not front:
                col = hexrgb(f.get("color", "#9CFF6B"))
                g = glow(col, int(asz * 1.6))
                paste(fr, g, ax, ay, (0.55 + 0.35 * math.sin(t * 6)) * min(1, lt / 0.3))
            if not front:
                continue
            if kind == "corazones":
                for j in range(7):
                    q = (lt - j * 0.22) / 1.4
                    if 0 <= q < 1:
                        hx = ax + (r.uniform(-0.6, 0.6)) * asz + 20 * math.sin(q * 9 + j)
                        hy = ay - q * asz * 0.9
                        sz = int(60 + 50 * r.random())
                        paste(fr, fx_sprite("corazon", sz), hx, hy, min(1, (1 - q) * 3) * min(1, q * 8))
            elif kind == "brillos":
                for j in range(6):
                    q = ((lt * 1.6 + j / 6) % 1)
                    rr = random.Random(int((lt * 1.6 + j / 6)) * 13 + j)
                    hx = ax + rr.uniform(-0.55, 0.55) * asz
                    hy = ay + rr.uniform(-0.5, 0.35) * asz
                    sz = int(80 * math.sin(q * math.pi)) + 4
                    paste(fr, fx_sprite("brillo", 100).resize((sz, sz)), hx, hy)
            elif kind in ("interrogacion", "exclamacion", "zzz"):
                ch = {"interrogacion": "?", "exclamacion": "!", "zzz": "zeta"}[kind]
                k = ease_out_back(lt / 0.3, 2.5)
                sz = max(4, int(150 * k))
                im = fx_sprite(ch, 160).resize((sz, sz))
                rot = 10 * math.sin(t * 5) if kind != "exclamacion" else 6 * math.sin(t * 30) * max(0, 1 - lt)
                im = im.rotate(rot, Image.BICUBIC, expand=True)
                dx = f.get("dx", 0.42)
                hy = ay - asz * 0.5 - (25 * ((lt * 0.8) % 1) if kind == "zzz" else 0)
                paste(fr, im, ax + dx * asz, hy)
            elif kind == "sudor":
                q = (lt % 1.2) / 1.2
                paste(fr, fx_sprite("sudor", 90), ax + asz * 0.36, ay - asz * 0.32 + q * 40, min(1, (1 - q) * 4))
            elif kind == "confeti":
                d = ImageDraw.Draw(fr)
                cols = [(255, 92, 120), (255, 214, 64), (90, 200, 255), (120, 230, 120), (190, 120, 255)]
                for j in range(70):
                    rr = random.Random(j * 7 + si)
                    sp = rr.uniform(300, 600)
                    xx = rr.uniform(0, W) + 40 * math.sin(lt * 3 + j)
                    yy = -50 + (lt - rr.uniform(0, 0.6)) * sp
                    if -40 < yy < H:
                        a = lt * rr.uniform(4, 9) + j
                        wv, hv = 14 * abs(math.cos(a)) + 3, 24
                        d.polygon([(xx - wv, yy - hv / 2), (xx + wv, yy - hv / 2 + 6), (xx + wv, yy + hv / 2),
                                   (xx - wv, yy + hv / 2 - 6)], fill=cols[j % 5])

    def frame_at(t):
        si = scene_at(t)
        sc = scenes[si]
        T = tl[si]
        fr = fondos[fkeys[si]].frame(t)
        prev = acts[si - 1] if si > 0 else None
        speaker = sc.get("habla")
        fi = int((t - T["start"]) * FPS)
        env_v = float(envs[si][fi]) if 0 <= fi < len(envs[si]) else 0.0
        # posición del que habla (para que los demás le miren)
        spk_pos = None
        if speaker in acts[si]:
            stt = actor_state(acts[si][speaker], si, t, prev)
            spk_pos = stt[:2] if stt else None
        pos = {}
        for k, A in acts[si].items():
            pos[k] = (A.x, A.y, 600 * A.s)
        fx_layer(fr, sc, si, t, pos, front=False)
        # actores que se van (estaban en la escena anterior y ya no)
        if prev and not whip[si]:
            lt = t - T["start"]
            if lt < 0.22:
                for k, P in prev.items():
                    if k in acts[si]:
                        continue
                    q = 1 - ease_out(lt / 0.22)
                    st = actor_state(P, si - 1, t, acts[si - 2] if si > 1 else None)
                    if st:
                        size = max(8, int(600 * P.s * q))
                        im = sprite(P.prop, max(8, int(600 * P.s)), 0, P.texto, P.expr, 0, False, (0, 0), P.gris).resize((size, size))
                        paste(fr, im, st[0], st[1])
        order = sorted(acts[si].values(), key=lambda A: (A.z, A.key == speaker))
        for A in order:
            r = draw_actor(fr, A, si, t, prev, speaker, spk_pos, env_v)
            if r:
                pos[A.key] = r
        fx_layer(fr, sc, si, t, pos, front=True)
        # rótulo
        if rots[si] is not None:
            lt = t - rot_t0[si]
            if lt >= 0:
                k = ease_out_back(lt / 0.32, 2.0)
                im = rots[si]
                wob = 1.5 * math.sin(t * 2.2)
                w2, h2 = max(4, int(im.width * k)), max(4, int(im.height * k))
                im2 = im.resize((w2, h2), Image.BILINEAR).rotate(wob, Image.BICUBIC, expand=True)
                paste(fr, im2, W / 2, ROT_Y + sc.get("rotulo_dy", 0))
        # subtítulos
        for a0, b0, im in caps:
            if a0 <= t < b0:
                k = ease_out_back((t - a0) / 0.13, 2.0)
                k = 0.85 + 0.15 * k
                im2 = im.resize((int(im.width * k), int(im.height * k)), Image.BILINEAR)
                paste(fr, im2, W / 2, CAP_Y)
                break
        return fr, si

    last_frames = {}

    def final_frame(t):
        fr, si = frame_at(t)
        T = tl[si]
        lt = t - T["start"]
        if whip[si] and lt < 0.26:
            p = ease_io(lt / 0.26)
            pf = last_frames.get(si - 1)
            if pf is None:
                pf, _ = frame_at(T["start"] - 1 / FPS)
            comp = Image.new("RGB", (W, H))
            off = int(W * p)
            comp.paste(pf, (-off, 0))
            comp.paste(fr, (W - off, 0))
            fr = comp
        cam = scenes[si].get("camara")
        if cam == "temblor" and lt < 0.5:
            dx = int(14 * math.sin(t * 90) * (1 - lt / 0.5))
            fr = Image.fromarray(np.roll(np.asarray(fr), dx, axis=1))
        if cam == "zoom":
            z = 1 + 0.06 * ease_io(lt / max(0.5, T["end"] - T["start"]))
            w2, h2 = int(W * z), int(H * z)
            fr = fr.resize((w2, h2), Image.BILINEAR).crop(((w2 - W) // 2, (h2 - H) // 2, (w2 - W) // 2 + W, (h2 - H) // 2 + H))
        if si + 1 < nS and whip[si + 1] and t + 1 / FPS >= T["end"]:
            last_frames[si] = fr
        return fr

    if only_frame is not None:
        si = max(0, min(nS - 1, only_frame - 1))
        T = tl[si]
        t = min(T["end"] - 0.05, T["vstart"] + T["vdur"] * 0.45)
        os.makedirs(SALIDA, exist_ok=True)
        p = os.path.join(SALIDA, f"prueba-{vid}-{si + 1}.png")
        final_frame(t).save(p)
        print(p)
        return p

    out = os.path.join(LISTOS, f"{name}.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-i", wav, "-map", "0:v", "-map", "1:a",
                           "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
                           "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-c:a", "aac", "-b:a", "192k",
                           "-shortest", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    nf = int(total * FPS)
    cover_t = tl[0]["vstart"] + min(1.2, tl[0]["vdur"] * 0.6)
    for i in range(nf):
        t = i / FPS
        fr = final_frame(t)
        if abs(t - cover_t) < 0.5 / FPS:
            fr.save(os.path.join(LISTOS, f"{name}-portada.jpg"), quality=92)
        ff.stdin.write(fr.tobytes())
    ff.stdin.close()
    ff.wait()

    # ---- texto para publicar
    tags = v.get("hashtags", [])
    txt = (f"TÍTULO (máx. 100 caracteres):\n{v['titulo']}\n\n"
           f"DESCRIPCIÓN:\n{v.get('descripcion', '')}\n\n{' '.join(tags)}\n\n"
           f"COMENTARIO FIJADO:\n{v.get('comentario', '¿Lo sabías? Cuéntamelo en los comentarios 👇')}\n\n"
           f"GUION:\n" + "\n".join(f"- {s.get('habla', '')}: {s['texto'].replace('*', '')}" for s in scenes) + "\n")
    with open(os.path.join(LISTOS, f"{name}.txt"), "w") as f:
        f.write(txt)
    subprocess.run(["rm", "-rf", tmp])
    print(f"OK {name}.mp4  {total:.1f} s")
    return out


def reparto():
    names = list(PJ.PERSONAJES)
    cols = 4
    rows = math.ceil(len(names) / cols)
    cw, chh = 420, 470
    sheet = Image.new("RGB", (cols * cw, rows * chh), (250, 244, 232))
    d = ImageDraw.Draw(sheet)
    exprs = PJ.CARAS
    for i, nm in enumerate(names):
        info = PJ.PERSONAJES[nm][1]
        im = sprite(nm, 380, 0, "243" if nm == "calendario" else None, exprs[i % len(exprs)], (i % 3), False, (0, 0))
        x, y = (i % cols) * cw, (i // cols) * chh
        sheet.paste(im, (x + 20, y + 10), im)
        lab = f"{nm}  ·  {exprs[i % len(exprs)] if info.get('cara') else 'sin cara'}"
        d.text((x + cw // 2, y + chh - 40), lab, font=font("inter", 26), fill=INK, anchor="mm")
    os.makedirs(SALIDA, exist_ok=True)
    p = os.path.join(SALIDA, "reparto.png")
    sheet.save(p)
    print(p)


def caras():
    """Hoja con todas las expresiones de un personaje (por defecto, Chispa)."""
    nm = sys.argv[2] if len(sys.argv) > 2 else "bombilla"
    exprs = PJ.CARAS
    sheet = Image.new("RGB", (len(exprs) * 300, 700), (250, 244, 232))
    d = ImageDraw.Draw(sheet)
    for i, e in enumerate(exprs):
        for j, b in enumerate((0, 2)):
            im = sprite(nm, 300, 0, None, e, b, False, (0, 0))
            sheet.paste(im, (i * 300, j * 320), im)
        d.text((i * 300 + 150, 670), e, font=font("inter", 26), fill=INK, anchor="mm")
    os.makedirs(SALIDA, exist_ok=True)
    p = os.path.join(SALIDA, f"caras-{nm}.png")
    sheet.save(p)
    print(p)


def guion(vid):
    v = load(vid)
    print(f"# {v['titulo']}\n# Pega esto en ElevenLabs (texto a voz), descarga el audio y guárdalo como pon-aqui-tu-voz/{v['id']}.mp3\n")
    for s in v["escenas"]:
        print(s["texto"].replace("*", "") + "\n")


def _render_safe(vid):
    try:
        return render(vid)
    except SystemExit as e:
        print(f"ERROR {vid}: {e}")


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else "lista"
    ids = sorted(os.path.basename(p).split("-")[0] for p in glob.glob(os.path.join(GUIONES, "*.json")))
    if cmd == "lista":
        for p in sorted(glob.glob(os.path.join(GUIONES, "*.json"))):
            v = json.load(open(p))
            print(f"{v['id']}  {v['titulo']}  ({len(v['escenas'])} escenas)")
    elif cmd == "render":
        want = ids if (len(args) < 2 or args[1] == "todos") else args[1:]
        if len(want) == 1:
            render(want[0])
        else:
            with ProcessPoolExecutor(max_workers=min(len(want), max(1, (os.cpu_count() or 2) - 1))) as ex:
                list(ex.map(_render_safe, want))
    elif cmd == "prueba":
        render(args[1], only_frame=int(args[2]) if len(args) > 2 else 1)
    elif cmd == "guion":
        guion(args[1])
    elif cmd == "reparto":
        reparto()
    elif cmd == "caras":
        caras()
    else:
        print(__doc__)
