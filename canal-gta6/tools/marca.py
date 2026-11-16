#!/usr/bin/env python3
"""Genera la identidad visual del canal: foto de perfil, banner y marca de agua.
Uso: python3 tools/marca.py   ->  marca/{perfil.png, banner.png, marca-de-agua.png}
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render as R

ACCENT = os.environ.get("ACENTO", "#ff4fa3")
NAME = R.CHANNEL
OUT = os.path.join(R.ROOT, "marca")
os.makedirs(OUT, exist_ok=True)
acc = R.hex2rgb(ACCENT)
gcol = R.mix(acc, (255, 255, 255), 0.15)


def scene(with_palms=True):
    fr = R.build_sky(ACCENT)
    fr[R.HORIZON:] = R.draw_floor(0.3, gcol)
    im = Image.fromarray(fr).convert("RGBA")
    if with_palms:
        im.alpha_composite(R.palm(1000, False, 1), (-170, R.H - 1000))
        im.alpha_composite(R.palm(860, True, 2), (R.W - 560, R.H - 860))
    return im


def big_text(d, xy_center, text, font, fill, stroke, shadow=10):
    bb = font.getbbox(text)
    x = xy_center[0] - (bb[2] - bb[0]) // 2 - bb[0]
    y = xy_center[1] - (bb[3] - bb[1]) // 2 - bb[1]
    d.text((x + shadow, y + shadow), text, font=font, fill=acc + (255,))
    d.text((x, y), text, font=font, fill=fill, stroke_width=stroke, stroke_fill=(15, 4, 26, 255))


# --- Banner 2560x1440 (zona segura central 1546x423) ---
bn = scene().resize((2560, 1440), Image.LANCZOS)
veil = Image.new("RGBA", bn.size, (0, 0, 0, 0))
ImageDraw.Draw(veil).rectangle([0, 470, 2560, 970], fill=(8, 2, 18, 110))
bn.alpha_composite(veil.filter(ImageFilter.GaussianBlur(40)))
d = ImageDraw.Draw(bn)
ft = R.fit_font(R.F_HEAD, NAME, 1440, 300)
big_text(d, (1280, 640), NAME, ft, (255, 255, 255, 255), 6, 12)
tag = "GUÍAS · TRUCOS · NOTICIAS DE GTA 6"
fs = R.fit_font(R.F_BOLD, tag, 1300, 64, 30)
bb = fs.getbbox(tag)
tw = bb[2] - bb[0]
y = 830
d.rounded_rectangle([1280 - tw // 2 - 40, y - 20, 1280 + tw // 2 + 40, y + 78], 24,
                    fill=(15, 4, 26, 235), outline=acc + (255,), width=5)
d.text((1280 - tw // 2 - bb[0], y - bb[1] + 4), tag, font=fs, fill=(255, 255, 255, 255))
bn.convert("RGB").save(os.path.join(OUT, "banner.png"), optimize=True)

# --- Foto de perfil 800x800 ---
full = scene(with_palms=False)
pf = full.crop((560, 180, 1360, 980))
d = ImageDraw.Draw(pf)
big_text(d, (400, 390), "ML", ImageFont.truetype(R.F_HEAD, 400), (255, 255, 255, 255), 9, 14)
pf.convert("RGB").save(os.path.join(OUT, "perfil.png"), optimize=True)

# --- Marca de agua 150x150 (PNG transparente) ---
wm = Image.new("RGBA", (600, 600), (0, 0, 0, 0))
d = ImageDraw.Draw(wm)
d.ellipse([20, 20, 580, 580], fill=(15, 4, 26, 200), outline=acc + (255,), width=24)
big_text(d, (300, 300), "ML", ImageFont.truetype(R.F_HEAD, 300), (255, 255, 255, 255), 6, 8)
wm.resize((150, 150), Image.LANCZOS).save(os.path.join(OUT, "marca-de-agua.png"))
print("OK", os.listdir(OUT))
