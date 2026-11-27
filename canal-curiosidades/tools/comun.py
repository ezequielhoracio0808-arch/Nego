"""Utilidades compartidas por las herramientas del canal."""
import json, os, re, subprocess, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "tools", "fonts")
F_HEAD = os.path.join(FONTS, "anton-latin-400-normal.woff")
F_BOLD = os.path.join(FONTS, "inter-latin-800-normal.woff")
F_REG = os.path.join(FONTS, "inter-latin-400-normal.woff")
UA = "dato-oculto-video-tools/1.0 (canal de curiosidades; herramienta propia)"

CFG = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
CANAL = os.environ.get("CANAL", CFG["canal"])


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def fit_font(path, text, maxw, start, minsize=30):
    from PIL import ImageFont
    s = start
    while s > minsize:
        f = ImageFont.truetype(path, s)
        if f.getbbox(text)[2] <= maxw:
            return f
        s -= 4
    return ImageFont.truetype(path, minsize)


def wrap(text, font, maxw):
    """Parte un texto en líneas que caben en maxw píxeles."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if font.getbbox(t)[2] <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def ruta_guion(arg):
    """Acepta una ruta, una fecha (AAAA-MM-DD) o un id (AAAA-MM-DD-slug)."""
    if os.path.exists(arg):
        return os.path.abspath(arg)
    gd = os.path.join(ROOT, "guiones")
    cands = sorted(f for f in os.listdir(gd) if f.startswith(arg) and f.endswith(".json"))
    if not cands:
        sys.exit(f"No encuentro el guion «{arg}» en guiones/")
    return os.path.join(gd, cands[-1])


def cargar_guion(arg):
    p = ruta_guion(arg)
    g = json.load(open(p, encoding="utf-8"))
    g["_id"] = os.path.splitext(os.path.basename(p))[0]
    g["_ruta"] = p
    return g


def trabajo(gid, *sub):
    d = os.path.join(ROOT, "trabajo", gid, *sub)
    os.makedirs(d, exist_ok=True)
    return d


def salida(gid):
    d = os.path.join(ROOT, "salida", gid)
    os.makedirs(d, exist_ok=True)
    return d


# ------------------------------------------------------------------ voz
def voz_path():
    if os.environ.get("PIPER_VOICE"):
        return os.environ["PIPER_VOICE"]
    name = CFG["voz"]["modelo"]
    d = os.path.expanduser("~/.cache/piper-voces")
    p = os.path.join(d, name + ".onnx")
    if not os.path.exists(p):
        os.makedirs(d, exist_ok=True)
        for ext in (".onnx", ".onnx.json"):
            print(f"Descargando voz {name}{ext} ...", flush=True)
            req = urllib.request.Request(CFG["voz"]["url"] + name + ext, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=600) as r, open(p.replace(".onnx", ext) + ".part", "wb") as f:
                f.write(r.read())
            os.replace(p.replace(".onnx", ext) + ".part", p.replace(".onnx", ext))
    return p


def pronunciar(text, extra=None):
    reglas = dict(CFG.get("pronunciacion", {}))
    reglas.update(extra or {})
    for a, b in reglas.items():
        text = re.sub(a, b, text)
    return text


def tts(text, path, extra_pron=None):
    """Sintetiza `text` en `path` (wav) y devuelve la duración en segundos."""
    import wave
    if not os.path.exists(path):
        subprocess.run([sys.executable, "-m", "piper", "-m", voz_path(), "-f", path,
                        "--length-scale", str(CFG["voz"].get("velocidad", 1.0)),
                        "--sentence-silence", "0.1"],
                       input=pronunciar(text, extra_pron).encode(), check=True, capture_output=True)
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()


def frases(text):
    """Divide la narración en frases (para sincronizar mejor los subtítulos)."""
    parts = re.split(r"(?<=[.!?…])\s+(?=[¿¡A-ZÁÉÍÓÚÑ0-9«\"])", text.strip())
    return [p.strip() for p in parts if p.strip()]


def ts(s):
    ms = int(round(s * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def mmss(s):
    s = int(s)
    return f"{s // 60}:{s % 60:02d}"
