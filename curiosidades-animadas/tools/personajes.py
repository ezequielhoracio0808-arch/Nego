"""Personajes y objetos de «Datos con Cara»: todo lo que sale en un short tiene cara.

Cada personaje se dibuja en un lienzo de 600x600 unidades (a doble resolución para
que los bordes salgan suaves) con colores planos y contorno grueso.

Para añadir uno nuevo:
  1. escribe una función  def p_nombre(L, fase, texto, boca):  que dibuje con L
     (L.ellipse, L.poly, L.tube, L.rrect, L.stroke, L.capa, L.texto ...)
  2. regístrala al final en PERSONAJES con dónde va la cara, su color de piel,
     si apoya en el suelo y el tono de voz.
Prueba:  python3 tools/animar.py reparto   (genera salida/reparto.png con todos)
"""
import math, random
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

SS = 2                     # superresolución de dibujo
N = 600                    # tamaño del lienzo en unidades
INK = (43, 27, 58)         # color del contorno
LW = 9                     # grosor de línea por defecto (unidades)
FONTS = None               # lo rellena animar.py


def font(name, size):
    return ImageFont.truetype(FONTS[name], size)


# ------------------------------------------------------------------ geometría
def bez(p0, p1, p2, p3, n=28):
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                    a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def arc(cx, cy, rx, ry, a0, a1, n=40, rot=0):
    out = []
    cr, sr = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        x, y = rx * math.cos(a), ry * math.sin(a)
        out.append((cx + x * cr - y * sr, cy + x * sr + y * cr))
    return out


def resample(pts, step):
    out = [pts[0]]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        dist = math.hypot(x1 - x0, y1 - y0)
        k = max(1, int(dist / step))
        for i in range(1, k + 1):
            out.append((x0 + (x1 - x0) * i / k, y0 + (y1 - y0) * i / k))
    return out


def blob(cx, cy, r, seed, k=7, amp=0.28, n=60):
    rng = random.Random(seed)
    ph = [rng.uniform(0, 6.28) for _ in range(3)]
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        rr = r * (1 + amp * (0.5 * math.sin(2 * a + ph[0]) + 0.3 * math.sin(3 * a + ph[1]) + 0.2 * math.sin(k * a + ph[2])))
        out.append((cx + rr * math.cos(a), cy + rr * 0.8 * math.sin(a)))
    return out


# ------------------------------------------------------------------ lienzo
class Lienzo:
    def __init__(self, im=None, n=N):
        self.k = SS
        self.im = im if im is not None else Image.new("RGBA", (n * SS, n * SS), INK + (0,))
        self.d = ImageDraw.Draw(self.im)

    def P(self, pts):
        return [(x * self.k, y * self.k) for x, y in pts]

    def capa(self):
        return Lienzo(n=self.im.width // self.k)

    def ellipse(self, cx, cy, rx, ry, fill, lw=LW, ink=INK):
        k, h = self.k, lw / 2
        if lw:
            self.d.ellipse([(cx - rx - h) * k, (cy - ry - h) * k, (cx + rx + h) * k, (cy + ry + h) * k], fill=ink)
            self.d.ellipse([(cx - rx + h) * k, (cy - ry + h) * k, (cx + rx - h) * k, (cy + ry - h) * k], fill=fill)
        else:
            self.d.ellipse([(cx - rx) * k, (cy - ry) * k, (cx + rx) * k, (cy + ry) * k], fill=fill)

    def circle(self, cx, cy, r, fill, lw=LW, ink=INK):
        self.ellipse(cx, cy, r, r, fill, lw, ink)

    def stroke(self, pts, lw=LW, ink=INK):
        P = self.P(pts)
        w = max(1, int(round(lw * self.k)))
        self.d.line(P, fill=ink, width=w, joint="curve")
        r = w / 2
        for x, y in (P[0], P[-1]):
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=ink)

    def poly(self, pts, fill, lw=LW, ink=INK):
        self.d.polygon(self.P(pts), fill=fill)
        if lw:
            self.stroke(list(pts) + [pts[0], pts[1]], lw, ink)

    def tube(self, pts, r0, r1, fill, lw=LW, ink=INK):
        s = resample(pts, 2.5)
        n = max(2, len(s))
        rs = [r0 + (r1 - r0) * i / (n - 1) for i in range(n)]
        k = self.k
        if lw:
            for (x, y), r in zip(s, rs):
                rr = r + lw / 2
                self.d.ellipse([(x - rr) * k, (y - rr) * k, (x + rr) * k, (y + rr) * k], fill=ink)
        for (x, y), r in zip(s, rs):
            rr = max(0.5, r - lw / 2)
            self.d.ellipse([(x - rr) * k, (y - rr) * k, (x + rr) * k, (y + rr) * k], fill=fill)

    def rrect(self, x0, y0, x1, y1, r, fill, lw=LW, ink=INK):
        k, h = self.k, lw / 2
        if lw:
            self.d.rounded_rectangle([(x0 - h) * k, (y0 - h) * k, (x1 + h) * k, (y1 + h) * k], radius=(r + h) * k, fill=ink)
        self.d.rounded_rectangle([(x0 + h) * k, (y0 + h) * k, (x1 - h) * k, (y1 - h) * k], radius=max(0, r - h) * k, fill=fill)

    def recorta(self, capa, mascara):
        """Pega `capa` sobre este lienzo, solo dentro de la silueta de `mascara`."""
        a = ImageChops.multiply(capa.im.getchannel("A"), mascara.im.getchannel("A"))
        capa.im.putalpha(a)
        self.im.alpha_composite(capa.im)

    def encima(self, capa):
        self.im.alpha_composite(capa.im)

    def texto(self, cx, cy, txt, size, fill, maxw=None, fuente="anton", stroke=0, ink=INK):
        k = self.k
        f = font(fuente, int(size * k))
        if maxw:
            while f.getlength(txt) > maxw * k and size > 10:
                size -= 4
                f = font(fuente, int(size * k))
        bb = self.d.textbbox((0, 0), txt, font=f, stroke_width=int(stroke * k))
        x = cx * k - (bb[0] + bb[2]) / 2
        y = cy * k - (bb[1] + bb[3]) / 2
        self.d.text((x, y), txt, font=f, fill=fill, stroke_width=int(stroke * k), stroke_fill=ink)


def contorno(im, extra=5):
    """Silueta exterior gruesa (estilo dibujo animado) alrededor de todo el personaje."""
    a = im.getchannel("A")
    sig = extra * SS / 1.8
    b = a.filter(ImageFilter.GaussianBlur(sig))
    m = b.point(lambda v: 255 if v > 14 else v * 18)
    base = Image.new("RGBA", im.size, INK + (0,))
    base.putalpha(m)
    base.alpha_composite(im)
    return base


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ------------------------------------------------------------------ caras
MOUTH = (92, 28, 48)
TONGUE = (240, 104, 120)
CARAS = ["feliz", "presumido", "sorprendido", "asustado", "enfadado", "triste", "pensativo", "dormido", "neutro"]


def _boca_forma(expr, nivel, fs):
    """Polígono de la boca abierta (en unidades relativas al centro de la boca)."""
    if expr in ("sorprendido", "asustado", "dormido"):
        rx, ry = (16, 20) if nivel <= 1 else (22, 30)
        if nivel == 0:
            rx, ry = 12, 15
        return arc(0, 0, rx * fs, ry * fs, 0, 360, 36)
    if expr in ("enfadado", "triste"):
        h = (14, 18, 30)[nivel]
        w = 30
        top = arc(0, h * 0.35 * fs, w * fs, h * 0.9 * fs, 180, 360, 20)
        return top + [(w * fs, h * 0.5 * fs), (-w * fs, h * 0.5 * fs)]
    # forma de D (feliz, presumido, neutro, pensativo)
    h = (16, 24, 38)[nivel]
    w = 34 if nivel else 30
    top = [(-w * fs, -6 * fs), (w * fs, -6 * fs)]
    return top + arc(0, -6 * fs, w * fs, h * fs, 0, 180, 24)


def cara(L, fx, fy, fs, expr="feliz", boca=0, parp=False, mira=(0, 0), piel=(255, 255, 255), sin_boca=False):
    lw = 6.5 * fs
    big = expr in ("sorprendido", "asustado")
    erx, ery = (34 * fs, 44 * fs) if big else (30 * fs, 38 * fs)
    ex, ey = 46 * fs, -12 * fs
    mx, my = mira
    # coloretes
    if expr in ("feliz", "presumido"):
        c = L.capa()
        for s in (-1, 1):
            c.ellipse(fx + s * 74 * fs, fy + 30 * fs, 20 * fs, 12 * fs, (255, 110, 140, 110), lw=0)
        L.encima(c)
    for s in (-1, 1):
        cx, cy = fx + s * ex, fy + ey
        top = cy - ery
        cerrado = parp or expr == "dormido"
        if cerrado:
            if expr == "feliz":
                L.stroke(arc(cx, cy + 6 * fs, erx * 0.9, ery * 0.55, 200, 340, 16), lw)
            else:
                L.stroke(arc(cx, cy - 2 * fs, erx * 0.9, ery * 0.4, 20, 160, 16), lw)
        else:
            L.ellipse(cx, cy, erx, ery, (255, 255, 255), lw)
            pr = (11 if big else 16) * fs
            px = cx + mx * (erx - pr - 6 * fs) * 0.85
            py = cy + my * (ery - pr - 6 * fs) * 0.85 + (8 * fs if expr == "presumido" else 0)
            L.ellipse(px, py, pr, pr, INK, lw=0)
            L.ellipse(px + 5 * fs, py - 6 * fs, 5 * fs, 5 * fs, (255, 255, 255), lw=0)
            if expr in ("presumido", "enfadado", "triste"):
                cut = cy - ery * (0.15 if expr == "presumido" else 0.45)
                pts = [p for p in arc(cx, cy, erx + 1, ery + 1, 180, 360, 40) if p[1] <= cut]
                if len(pts) > 2:
                    L.poly(pts, piel, lw=0)
                    L.stroke([(pts[0][0], cut), (pts[-1][0], cut)], lw)
                L.d.ellipse([(cx - erx - lw / 2) * L.k, (cy - ery - lw / 2) * L.k, (cx + erx + lw / 2) * L.k,
                             (cy + ery + lw / 2) * L.k], outline=INK, width=int(lw * L.k))
        # cejas
        b = 8 * fs
        if expr == "enfadado":
            L.stroke([(cx + s * 30 * fs, top - 18 * fs), (cx - s * 24 * fs, top + 2 * fs)], b)
        elif expr == "triste":
            L.stroke([(cx + s * 28 * fs, top - 2 * fs), (cx - s * 22 * fs, top - 20 * fs)], b)
        elif big:
            L.stroke(arc(cx, top - 4 * fs, 24 * fs, 16 * fs, 200, 340, 12), b)
        elif expr == "pensativo":
            if s > 0:
                L.stroke(arc(cx, top - 4 * fs, 24 * fs, 14 * fs, 200, 340, 12), b)
            else:
                L.stroke([(cx - 24 * fs, top - 6 * fs), (cx + 22 * fs, top - 8 * fs)], b)
        elif expr == "presumido":
            if s > 0:
                L.stroke(arc(cx, top - 6 * fs, 24 * fs, 14 * fs, 200, 340, 12), b)
    if sin_boca:
        return
    # boca
    bx, by = fx, fy + 60 * fs
    if boca == 0 and expr in ("presumido", "asustado", "enfadado", "triste", "pensativo", "neutro"):
        if expr == "presumido":
            L.stroke(bez((bx - 28 * fs, by + 2 * fs), (bx - 6 * fs, by + 14 * fs), (bx + 18 * fs, by + 8 * fs), (bx + 34 * fs, by - 12 * fs), 16), lw)
        elif expr == "asustado":
            L.stroke([(bx + x * fs, by + 5 * fs * math.sin(x * 0.32)) for x in range(-30, 31, 3)], lw)
        elif expr == "enfadado":
            L.stroke(arc(bx, by + 14 * fs, 26 * fs, 14 * fs, 200, 340, 16), lw)
        elif expr == "triste":
            L.stroke(arc(bx, by + 16 * fs, 22 * fs, 14 * fs, 205, 335, 16), lw)
        elif expr == "pensativo":
            L.stroke([(bx - 4 * fs, by + 4 * fs), (bx + 24 * fs, by - 2 * fs)], lw)
        else:
            L.stroke(arc(bx, by - 8 * fs, 22 * fs, 10 * fs, 30, 150, 12), lw)
        return
    forma = [(bx + x, by + y) for x, y in _boca_forma(expr, boca, fs)]
    m = L.capa()
    m.poly(forma, MOUTH, lw=0)
    inside = L.capa()
    inside.poly(forma, MOUTH, lw=0)
    ys = [p[1] for p in forma]
    y0, y1 = min(ys), max(ys)
    hh = y1 - y0
    inside.ellipse(bx, y1 - hh * 0.05, 22 * fs, hh * 0.42, TONGUE, lw=0)
    if boca >= 2:
        inside.d.rectangle([(bx - 40 * fs) * L.k, y0 * L.k, (bx + 40 * fs) * L.k, (y0 + 8 * fs) * L.k], fill=(255, 255, 255))
    L.recorta(inside, m)
    L.stroke(forma + [forma[0], forma[1]], lw)


# ------------------------------------------------------------------ personajes
def p_bombilla(L, fase, texto, boca):
    Y = (255, 233, 128)
    L.poly([(222, 360), (378, 360), (352, 452), (248, 452)], Y)
    L.circle(300, 228, 178, Y)
    c = L.capa()
    c.ellipse(212, 150, 26, 52, (255, 255, 255, 170), lw=0)
    c.ellipse(236, 90, 10, 12, (255, 255, 255, 170), lw=0)
    L.encima(c)
    G = (168, 177, 196)
    L.rrect(240, 446, 360, 478, 12, G)
    L.rrect(246, 474, 354, 506, 12, mix(G, (255, 255, 255), 0.2))
    L.rrect(252, 502, 348, 532, 12, G)
    L.ellipse(300, 546, 26, 16, INK, lw=0)


def p_pulpo(L, fase, texto, boca):
    C = (236, 104, 160)
    D = mix(C, INK, 0.18)
    for order in (1, 0):
        for i in range(8):
            if i % 2 != order:
                continue
            a = (i - 3.5) / 3.5
            bx = 300 + (i - 3.5) * 34
            w = 16 * math.sin(fase * math.pi / 2 + i * 1.3)
            pts = bez((bx, 300), (bx + a * 40, 470), (300 + a * 230, 575 + w * 0.5), (300 + a * 268 + w, 468 - abs(a) * 10 + w), 40)
            L.tube(pts, 36 - abs(a) * 4, 11, D if order else C)
            if not order:
                for j in range(8, 34, 7):
                    x, y = pts[j]
                    L.ellipse(x, y + 12, 7, 6, (255, 196, 220), lw=0)
    L.ellipse(300, 222, 178, 172, C)
    c = L.capa()
    for x, y, r in ((200, 120, 16), (380, 108, 12), (410, 170, 9), (172, 196, 10), (330, 74, 9)):
        c.ellipse(x, y, r, r * 0.85, mix(C, (255, 255, 255), 0.35) + (255,), lw=0)
    c.ellipse(215, 120, 34, 22, (255, 255, 255, 90), lw=0)
    L.encima(c)


def heart_pts(cx, cy, s, n=80):
    out = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        out.append((cx + x * s, cy - y * s))
    return out


def p_corazon(L, fase, texto, boca):
    C = (238, 64, 88)
    L.poly(heart_pts(300, 290, 15.5), C)
    c = L.capa()
    c.ellipse(190, 190, 30, 44, (255, 255, 255, 120), lw=0)
    L.encima(c)


def drop_pts(cx, cy, r, tip):
    pts = arc(cx, cy, r, r, -25, 205, 40)
    return bez((cx + r * math.cos(math.radians(205)), cy + r * math.sin(math.radians(205))),
               (cx - r * 0.85, cy - r * 0.9), (cx - 20, tip + 60), (cx, tip), 16) + \
        bez((cx, tip), (cx + 20, tip + 60), (cx + r * 0.85, cy - r * 0.9),
            (cx + r * math.cos(math.radians(-25)), cy + r * math.sin(math.radians(-25))), 16) + pts


def p_gota(L, fase, texto, boca):
    C = (70, 132, 246)
    L.poly(drop_pts(300, 370, 165, 40), C)
    c = L.capa()
    c.ellipse(205, 300, 24, 44, (255, 255, 255, 140), lw=0)
    L.encima(c)


def _planeta(L, base, bandas, r=232):
    L.circle(300, 300, r, base)
    m = L.capa(); m.circle(300, 300, r - 4, base, lw=0)
    c = L.capa()
    bandas(c)
    L.recorta(c, m)
    # sombra suave en la parte de abajo a la derecha
    s2 = L.capa()
    s2.circle(300, 300, r, (0, 0, 0, 40), lw=0)
    s3 = L.capa(); s3.circle(250, 250, r * 0.98, (0, 0, 0, 255), lw=0)
    a = ImageChops.subtract(s2.im.getchannel("A"), s3.im.getchannel("A"))
    s2.im.putalpha(a)
    L.encima(s2)
    hl = L.capa(); hl.ellipse(205, 175, 46, 30, (255, 255, 255, 80), lw=0)
    L.encima(hl)
    L.d.ellipse([(300 - r - LW / 2) * SS, (300 - r - LW / 2) * SS, (300 + r + LW / 2) * SS, (300 + r + LW / 2) * SS],
                outline=INK, width=int(LW * SS))


def p_venus(L, fase, texto, boca):
    def bandas(c):
        for y, h, col in ((110, 40, (250, 214, 140)), (190, 34, (226, 150, 66)), (300, 46, (250, 214, 140)),
                          (400, 32, (226, 150, 66)), (480, 38, (250, 214, 140))):
            pts = [(x, y + 14 * math.sin(x / 55 + y)) for x in range(40, 561, 20)]
            pts += [(x, y + h + 14 * math.sin(x / 60 + y * 1.7)) for x in range(560, 39, -20)]
            c.poly(pts, col + (255,), lw=0)
    _planeta(L, (242, 184, 90), bandas)


def p_tierra(L, fase, texto, boca):
    def bandas(c):
        G = (104, 196, 92)
        for cx, cy, r, sd in ((180, 210, 95, 1), (420, 330, 110, 2), (230, 470, 70, 3), (470, 140, 50, 4)):
            c.poly(blob(cx, cy, r, sd), G + (255,), lw=7)
        c.ellipse(300, 52, 170, 40, (245, 250, 255, 255), lw=0)
        c.ellipse(300, 556, 150, 36, (245, 250, 255, 255), lw=0)
        for x, y, w in ((140, 330, 90), (380, 230, 80), (330, 430, 100)):
            c.rrect(x, y, x + w, y + 16, 8, (255, 255, 255, 150), lw=0)
    _planeta(L, (60, 150, 236), bandas)


def p_sol(L, fase, texto, boca):
    R = (255, 158, 38)
    rot = fase * 7.5
    for i in range(12):
        a = math.radians(i * 30 + rot)
        a1, a2 = a - 0.16, a + 0.16
        pts = [(300 + 190 * math.cos(a1), 300 + 190 * math.sin(a1)),
               (300 + 286 * math.cos(a), 300 + 286 * math.sin(a)),
               (300 + 190 * math.cos(a2), 300 + 190 * math.sin(a2))]
        L.poly(pts, R)
    L.circle(300, 300, 200, (255, 212, 58))
    c = L.capa(); c.ellipse(215, 190, 40, 26, (255, 255, 255, 110), lw=0)
    L.encima(c)


def p_calendario(L, fase, texto, boca):
    L.rrect(110, 125, 490, 525, 30, (252, 249, 240))
    L.rrect(110, 125, 490, 238, 30, (232, 72, 72))
    L.d.rectangle([(110 + LW / 2) * SS, 200 * SS, (490 - LW / 2) * SS, (238 - LW / 2) * SS], fill=(232, 72, 72))
    L.stroke([(110, 238), (490, 238)], LW)
    for x in (200, 400):
        L.rrect(x - 14, 88, x + 14, 158, 12, (180, 186, 200))
    L.texto(300, 182, "DÍAS", 64, (255, 255, 255))
    L.texto(300, 384, texto or "365", 190, INK, maxw=330)


def p_cartel(L, fase, texto, boca):
    W_ = (214, 160, 98)
    L.rrect(284, 300, 316, 575, 10, mix(W_, INK, 0.25))
    L.rrect(60, 110, 540, 330, 22, W_)
    for y in (180, 255):
        L.stroke([(76, y), (524, y)], 4, mix(W_, INK, 0.4))
    L.texto(300, 220, texto or "¡OJO!", 120, INK, maxw=420)


def p_platano(L, fase, texto, boca):
    Y = (255, 221, 74)
    outer = bez((88, 150), (110, 610), (490, 610), (512, 150), 40)
    inner = bez((470, 186), (440, 360), (160, 360), (130, 186), 40)
    L.poly(outer + inner, Y)
    sh = L.capa()
    band = bez((470, 186), (440, 360), (160, 360), (130, 186), 40)
    band2 = bez((150, 230), (190, 420), (410, 420), (450, 230), 40)
    sh.poly(band + band2[::-1], (236, 190, 40, 255), lw=0)
    m = L.capa(); m.poly(outer + inner, Y, lw=0)
    L.recorta(sh, m)
    L.stroke(inner, LW)
    L.rrect(500, 122, 538, 170, 10, (120, 86, 48))
    L.ellipse(98, 168, 16, 18, (96, 66, 40), lw=6)


def p_tarro(L, fase, texto, boca):
    A = (247, 176, 44)
    L.rrect(140, 196, 460, 548, 74, A)
    hl = L.capa(); hl.rrect(168, 250, 200, 480, 16, (255, 255, 255, 90), lw=0)
    L.encima(hl)
    drip = [(140, 200), (460, 200), (460, 240)]
    for x, d in ((430, 30), (380, 70), (330, 30), (270, 60), (210, 26), (170, 48)):
        drip += [(x + 18, 240), (x + 18, 240 + d - 14)] + arc(x, 240 + d - 14, 18, 18, 0, 180, 10) + [(x - 18, 240)]
    drip += [(140, 240)]
    dr = L.capa(); dr.poly(drip, (226, 140, 18, 255), lw=0)
    m = L.capa(); m.rrect(140, 196, 460, 548, 74, A, lw=0)
    L.recorta(dr, m)
    L.rrect(160, 128, 440, 206, 22, (178, 110, 58))
    for x in range(190, 430, 40):
        L.stroke([(x, 140), (x, 196)], 4, mix((178, 110, 58), INK, 0.35))
    L.rrect(205, 448, 395, 520, 24, (255, 244, 214), lw=7)
    L.texto(300, 484, "MIEL", 50, (200, 110, 20))


def p_abeja(L, fase, texto, boca):
    Yb = (255, 204, 40)
    up = fase % 2 == 0
    wl = L.capa()
    for sg in (-1, 1):
        rot = (-38 if up else -14) * sg
        wl.poly(arc(300 + sg * 150, 150 if up else 168, 58, 92, 0, 360, 40, rot=rot), (214, 240, 255, 215), lw=7)
    L.encima(wl)
    for sg in (-1, 1):
        L.tube(bez((300 + sg * 38, 200), (300 + sg * 46, 130), (300 + sg * 70, 100), (300 + sg * 84, 62), 16), 6, 6, INK, lw=0)
        L.circle(300 + sg * 86, 58, 17, INK, lw=0)
    L.poly([(274, 462), (326, 462), (300, 548)], INK, lw=4)
    L.ellipse(300, 320, 176, 152, Yb)
    st = L.capa()
    for y0 in (366, 428):
        top = [(x, y0 + 26 * (1 - ((x - 300) / 180) ** 2)) for x in range(110, 491, 10)]
        bot = [(x, y + 30) for x, y in reversed(top)]
        st.poly(top + bot, INK + (255,), lw=0)
    m = L.capa(); m.ellipse(300, 320, 176, 152, Yb, lw=0)
    L.recorta(st, m)
    c = L.capa(); c.ellipse(190, 230, 30, 20, (255, 255, 255, 110), lw=0)
    L.encima(c)


def p_piramide(L, fase, texto, boca):
    S = (234, 192, 120)
    tri = [(52, 548), (300, 96), (548, 548)]
    L.poly(tri, S)
    c = L.capa()
    c.poly([(300, 96), (548, 548), (330, 548)], (206, 158, 92, 255), lw=0)
    for i, y in enumerate(range(160, 548, 48)):
        c.stroke([(0, y), (600, y)], 3.5, INK + (90,))
        for x in range(0 + (i % 2) * 40, 600, 80):
            c.stroke([(x, y), (x, y + 48)], 3.5, INK + (90,))
    m = L.capa(); m.poly(tri, S, lw=0)
    L.recorta(c, m)
    L.stroke(tri + [tri[0], tri[1]], LW)


def p_flamenco(L, fase, texto, boca):
    P = (255, 140, 172)
    Pd = (236, 108, 146)
    L.tube([(318, 400), (318, 500), (318, 580)], 8, 8, Pd)
    L.tube([(346, 400), (402, 468), (338, 486)], 8, 8, Pd)
    L.poly([(296, 580), (346, 580), (318, 566)], Pd, lw=6)
    L.poly([(430, 330), (520, 300), (500, 350), (440, 380)], Pd)
    L.ellipse(330, 360, 146, 86, P)
    w = L.capa(); w.ellipse(370, 350, 92, 48, Pd + (255,), lw=7)
    L.encima(w)
    neck = bez((210, 340), (110, 250), (300, 230), (232, 130), 40)
    L.tube(neck, 22, 18, P)
    L.circle(232, 112, 64, P)
    # pico: la parte de abajo se abre al hablar
    op = (0, 9, 18)[boca]
    BK = (250, 240, 228)
    up = [(284, 84), (338, 92), (366, 122), (374, 164), (364, 198), (350, 162), (328, 134), (290, 126)]
    lo = [(290, 126), (326, 136 + op * 0.5), (344, 164 + op), (352, 200 + op), (338, 194 + op), (318, 160 + op * 0.6), (286, 140)]
    for shape in (lo, up):
        L.poly(shape, BK, lw=0)
        tip = L.capa(); tip.poly([(300, 162 + (op if shape is lo else 0)), (420, 150), (420, 240), (300, 240)], INK + (255,), lw=0)
        mk = L.capa(); mk.poly(shape, (0, 0, 0), lw=0)
        L.recorta(tip, mk)
        L.stroke(shape + [shape[0], shape[1]], LW * 0.8)


def p_gamba(L, fase, texto, boca):
    O = (255, 132, 98)
    Ol = (255, 176, 140)
    cx, cy, R = 300, 330, 122
    for k in (0, 1):
        L.tube(bez((452, 200 + k * 14), (520, 40), (330, 0), (130 + k * 50, 58 + k * 30), 40), 3.5, 2.5, INK, lw=0)
    segs = []
    for i, (ang, r) in enumerate(((-110, 90), (-145, 84), (-180, 76), (-215, 68), (-250, 58), (-282, 48))):
        a = math.radians(ang)
        segs.append((cx + R * math.cos(a), cy + R * math.sin(a), r, ang))
    for x, y, r, ang in segs[:5]:
        a = math.radians(ang)
        x0, y0 = x - (r * 0.7) * math.cos(a), y - (r * 0.7) * math.sin(a)
        L.stroke([(x0, y0), (x0 - 34 * math.cos(a) + 10, y0 - 34 * math.sin(a) + 12)], 7)
    tx, ty = segs[-1][0] + 34, segs[-1][1] + 22
    for ang in (5, 40, 75):
        L.poly(arc(tx + 44 * math.cos(math.radians(ang)), ty + 44 * math.sin(math.radians(ang)), 46, 18, 0, 360, 30, rot=ang), Ol, lw=7)
    for x, y, r, ang in reversed(segs):
        L.poly(arc(x, y, r, 42, 0, 360, 44, rot=ang), O)
        c = L.capa(); c.poly(arc(x, y, r * 0.55, 16, 0, 360, 30, rot=ang), (255, 255, 255, 70), lw=0)
        L.encima(c)
    L.poly([(440, 176), (548, 120), (470, 214)], Ol, lw=7)
    L.poly(arc(398, 252, 118, 98, 0, 360, 60, rot=-30), O)
    c = L.capa(); c.ellipse(350, 196, 34, 18, (255, 255, 255, 90), lw=0)
    L.encima(c)


# nombre: (función, info)
#   cara = (x, y, escala) de la cara en el lienzo, o None si no tiene cara
#   suelo = True si se apoya en el suelo (sombra debajo); False si flota
#   pie = altura (en el lienzo) donde apoya, para colocar la sombra
#   voz = tono de voz (1 = normal, >1 más agudo, <1 más grave)
#   fases = nº de dibujos distintos que alterna (aleteo, tentáculos...)
PERSONAJES = {
    "bombilla":   (p_bombilla,   dict(cara=(300, 226, 1.3), piel=(255, 233, 128), suelo=True, pie=560, voz=1.12, nombre="Chispa (la bombilla)")),
    "pulpo":      (p_pulpo,      dict(cara=(300, 238, 1.32), piel=(236, 104, 160), suelo=True, pie=585, voz=1.0, fases=4)),
    "corazon":    (p_corazon,    dict(cara=(300, 280, 1.15), piel=(238, 64, 88), suelo=False, voz=1.22)),
    "gota":       (p_gota,       dict(cara=(300, 372, 1.15), piel=(70, 132, 246), suelo=False, voz=1.28)),
    "venus":      (p_venus,      dict(cara=(300, 296, 1.4), piel=(242, 184, 90), suelo=False, voz=1.1)),
    "tierra":     (p_tierra,     dict(cara=(300, 296, 1.4), piel=(60, 150, 236), suelo=False, voz=0.96)),
    "sol":        (p_sol,        dict(cara=(300, 296, 1.35), piel=(255, 212, 58), suelo=False, voz=0.82, fases=4)),
    "calendario": (p_calendario, dict(cara=None, suelo=False)),
    "cartel":     (p_cartel,     dict(cara=None, suelo=True, pie=578)),
    "platano":    (p_platano,    dict(cara=(300, 396, 1.0), piel=(255, 221, 74), suelo=True, pie=505, voz=1.06)),
    "tarro":      (p_tarro,      dict(cara=(300, 326, 1.2), piel=(247, 176, 44), suelo=True, pie=552, voz=0.98)),
    "abeja":      (p_abeja,      dict(cara=(300, 282, 1.08), piel=(255, 204, 40), suelo=False, voz=1.32, fases=2, rapido=True)),
    "piramide":   (p_piramide,   dict(cara=(300, 398, 1.2), piel=(234, 192, 120), suelo=True, pie=552, voz=0.8)),
    "flamenco":   (p_flamenco,   dict(cara=(228, 104, 0.62), piel=(255, 140, 172), suelo=True, pie=588, voz=1.04, boca_propia=True)),
    "gamba":      (p_gamba,      dict(cara=(400, 246, 0.9), piel=(255, 136, 100), suelo=False, voz=1.3)),
}
