#!/usr/bin/env python3
"""Identidad visual del canal: foto de perfil, banner y marca de agua.
Uso: python3 tools/marca.py   ->  marca/{perfil.png, banner.png, marca-de-agua.png}
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun as C
from producir import cerradura, fondo_marca, FONDO

OUT = os.path.join(C.ROOT, "marca")
os.makedirs(OUT, exist_ok=True)
acc = C.hex2rgb(C.CFG["acento"])
oscuro = FONDO + (255,)


def estrellas(im, n, seed):
    rnd = np.random.default_rng(seed)
    d = ImageDraw.Draw(im)
    for _ in range(n):
        x, y = rnd.integers(0, im.width), rnd.integers(0, im.height)
        r = rnd.choice([1, 1, 1, 2])
        a = int(rnd.integers(60, 200))
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, a))


def halo(size, r, color, blur):
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([size[0] / 2 - r, size[1] / 2 - r, size[0] / 2 + r, size[1] / 2 + r], fill=color)
    return im.filter(ImageFilter.GaussianBlur(blur))


# --- Foto de perfil 800×800: cerradura dorada sobre fondo nocturno ---
pf = fondo_marca((800, 800), acc, 3).convert("RGBA")
estrellas(pf, 120, 1)
pf.alpha_composite(halo((800, 800), 300, acc + (90,), 60))
pf.alpha_composite(cerradura(560, oscuro, acc + (255,)), (120, 120))
pf.convert("RGB").save(os.path.join(OUT, "perfil.png"), optimize=True)

# --- Banner 2560×1440 (zona segura centrada de 1546×423) ---
bn = fondo_marca((2560, 1440), acc, 5).convert("RGBA")
estrellas(bn, 900, 2)
glow = Image.new("RGBA", bn.size, (0, 0, 0, 0))
ImageDraw.Draw(glow).ellipse([780, 420, 1780, 1020], fill=acc + (70,))
bn.alpha_composite(glow.filter(ImageFilter.GaussianBlur(140)))
d = ImageDraw.Draw(bn)
icon = cerradura(250, oscuro, acc + (255,))
f = C.fit_font(C.F_HEAD, C.CANAL, 1080, 240, 80)
bb = f.getbbox(C.CANAL)
tw = bb[2] - bb[0]
total = 250 + 50 + tw
x0 = (2560 - total) // 2
bn.alpha_composite(icon, (x0, 720 - 125 - 40))
tx, ty = x0 + 300 - bb[0], 720 - 40 - (bb[3] + bb[1]) // 2
d.text((tx + 8, ty + 10), C.CANAL, font=f, fill=(0, 0, 0, 200))
d.text((tx, ty), C.CANAL, font=f, fill=(255, 255, 255, 255))
fs = C.fit_font(C.F_BOLD, C.CFG["eslogan"], 1300, 56, 28)
sb = fs.getbbox(C.CFG["eslogan"])
d.text(((2560 - (sb[2] - sb[0])) // 2 - sb[0], 860), C.CFG["eslogan"], font=fs, fill=acc + (255,))
bn.convert("RGB").save(os.path.join(OUT, "banner.png"), optimize=True)

# --- Marca de agua 150×150 (PNG transparente) ---
cerradura(600, (10, 12, 22, 200), acc + (255,)).resize((150, 150), Image.LANCZOS).save(os.path.join(OUT, "marca-de-agua.png"))
print("OK", sorted(os.listdir(OUT)))
