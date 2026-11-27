#!/usr/bin/env python3
"""Imagen del canal El Dato Oculto con los personajes de «Datos con Cara».

Uso:  python3 tools/marca.py   ->  canal/banner.png (2560x1440) y canal/perfil-chispa.png (800x800)
"""
import math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import animar as A

OUT = os.path.join(A.ROOT, "canal")
os.makedirs(OUT, exist_ok=True)
NAME = A.CANAL.upper()
TAG = "Curiosidades, historia y misterios que casi nadie te cuenta"


def rays(w, h, cx, cy, c1, c2, n=18):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    ang = np.arctan2(y - cy, x - cx)
    m = np.clip(np.sin(ang * n) * 3 + 0.5, 0, 1)[..., None]
    r = np.hypot(x - cx, y - cy) / max(w, h)
    vig = (1 - 0.55 * np.clip(r * 1.6, 0, 1) ** 1.4)[..., None]
    a = (np.array(c1, np.float32) * (1 - m) + np.array(c2, np.float32) * m) * vig
    return Image.fromarray(a.astype(np.uint8)).convert("RGBA")


def put(im, name, size, cx, cy, expr="feliz", texto=None, mira=(0, 0)):
    sp = A.sprite(name, size, 0, texto, expr, 0, False, mira)
    im.alpha_composite(sp, (int(cx - size / 2), int(cy - size / 2)))


# ---------------------------------------------------------------- banner 2560x1440
# Zona visible en todos los dispositivos: 1546x423 en el centro (x 507-2053, y 508-931).
# En ordenador se ve toda la franja horizontal y 508-931: ahí van los personajes de los lados.
W, H = 2560, 1440
bn = rays(W, H, W / 2, 720, (44, 26, 92), (62, 38, 122))
put(bn, "venus", 210, 430, 610, "presumido", mira=(1, 0))
put(bn, "pulpo", 400, 230, 735, "feliz", mira=(1, 0))
put(bn, "abeja", 160, 2150, 600, "feliz", mira=(-1, 0))
put(bn, "flamenco", 410, 2390, 722, "feliz", mira=(-1, 0))
put(bn, "platano", 230, 2170, 826, "presumido", mira=(-1, 0))
title = A.text_img([[(w, i == 2, False) for i, w in enumerate(NAME.split())]], "anton", 230, 1060, 16, shadow_off=16, spacing=1.0)
bn.alpha_composite(title, (int(1215 - title.width / 2), int(672 - title.height / 2)))
tag = A.text_img([[(w, False, False) for w in TAG.split()]], "inter", 54, 1200, 9)
bn.alpha_composite(tag, (int(W / 2 - tag.width / 2), int(852 - tag.height / 2)))
put(bn, "bombilla", 230, 1215 + title.width / 2 + 95, 668, "presumido", mira=(-1, 0))
bn.convert("RGB").save(os.path.join(OUT, "banner.png"), optimize=True)

# ---------------------------------------------------------------- foto de perfil alternativa 800x800
pf = rays(800, 800, 400, 400, (255, 196, 61), (255, 222, 120), n=12)
put(pf, "bombilla", 700, 400, 430, "presumido")
pf.convert("RGB").save(os.path.join(OUT, "perfil-chispa.png"), optimize=True)

# vista previa de cómo se ve el banner en el móvil (solo la zona segura) y en el ordenador
prev = Image.new("RGB", (W, H + 40), (255, 255, 255))
prev.paste(bn.convert("RGB"), (0, 0))
dd = ImageDraw.Draw(prev)
dd.rectangle([507, 508, 2053, 931], outline=(255, 60, 60), width=6)
dd.rectangle([0, 508, W - 1, 931], outline=(60, 200, 255), width=4)
prev.resize((W // 4, (H + 40) // 4)).save(os.path.join(A.SALIDA, "_banner-zonas.png"))
print("OK", sorted(os.listdir(OUT)))
