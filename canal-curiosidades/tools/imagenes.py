#!/usr/bin/env python3
"""Descarga las imágenes de un guion desde Wikimedia Commons (y Openverse como reserva),
solo con licencias que permiten uso comercial y modificación, y guarda la atribución.

Uso:  python3 tools/imagenes.py <guion|fecha> [--forzar h3 s1 ...]
      python3 tools/imagenes.py --buscar "texto"     (lista candidatas de Commons sin descargar)
  El campo "imagen" de cada escena puede ser:
    "texto de búsqueda"          -> busca en Commons (mejor en inglés: hay muchas más fotos)
    "File:Nombre exacto.jpg"     -> esa imagen concreta de Commons
    "@fondo"                     -> fondo oscuro de la marca (para cifras o frases a pantalla completa)
  --forzar 3 5   descarta la imagen elegida para esas escenas y prueba la siguiente candidata.
Salida: trabajo/<id>/img/  (imágenes + creditos.json) y trabajo/<id>/contacto.jpg para revisarlas.
"""
import argparse, hashlib, html, json, os, re, sys, time
import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun as C

COMMONS = "https://commons.wikimedia.org/w/api.php"
OPENVERSE = "https://api.openverse.org/v1/images/"
S = requests.Session()
S.headers["User-Agent"] = C.UA
OK_LIC = re.compile(r"^(cc0|cc[ -]by(-sa)?([ -]\d\.\d)?.*|public domain|pd.*|attribution|no restrictions|cc-pd.*)$", re.I)
BAD_LIC = re.compile(r"\b(nc|nd)\b|fair use|^gfdl$", re.I)


def limpio(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def get(url, **kw):
    for i in range(4):
        r = S.get(url, timeout=60, **kw)
        if r.status_code != 429:
            return r
        time.sleep(5 * (i + 1) ** 2)
    return r


def licencia_ok(lic):
    lic = (lic or "").strip()
    return bool(lic) and bool(OK_LIC.match(lic)) and not BAD_LIC.search(lic)


def thumb(info):
    """URL de una miniatura en tamaño estándar (Wikimedia limita los originales y tamaños raros)."""
    w = info["width"]
    size = 3840 if w >= 3840 else 1920 if w >= 1920 else 960 if w >= 960 else None
    if not size:
        return None, 0
    url = info["url"].split("?")[0]
    m = re.match(r"https://upload\.wikimedia\.org/wikipedia/commons/(\w)/(\w\w)/(.+)$", url)
    if not m:
        return None, 0
    name = m.group(3)
    return f"https://upload.wikimedia.org/wikipedia/commons/thumb/{m.group(1)}/{m.group(2)}/{name}/{size}px-{name}", size


def candidatos_commons(spec):
    """Candidatas de Commons; si la búsqueda no da nada, la repite quitando palabras del final."""
    out = _commons(spec)
    words = spec.split()
    while not out and not spec.startswith("File:") and len(words) > 2:
        words = words[:-1]
        out = _commons(" ".join(words))
    return out


def _commons(spec):
    params = dict(action="query", format="json", prop="imageinfo", iiprop="url|size|mime|extmetadata",
                  iiextmetadatafilter="LicenseShortName|Artist|Credit|UsageTerms")
    if spec.startswith("File:"):
        params["titles"] = spec
    else:
        params.update(generator="search", gsrsearch=f"{spec} filetype:bitmap", gsrnamespace=6, gsrlimit=20)
    r = get(COMMONS, params=params)
    pages = r.json().get("query", {}).get("pages", {}) if r.ok else {}
    out = []
    for p in sorted(pages.values(), key=lambda p: p.get("index", 0)):
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("mime") not in ("image/jpeg", "image/png"):
            continue
        m = ii.get("extmetadata", {})
        lic = m.get("LicenseShortName", {}).get("value", "")
        if not licencia_ok(lic):
            continue
        url, size = thumb(ii)
        if not url:
            continue
        ar = ii["width"] / max(ii["height"], 1)
        score = (2 if 1.25 <= ar <= 2.1 else 1 if ar >= 1 else 0) + (1 if ii["width"] >= 1920 else 0) - out.__len__() * 0.05
        autor = limpio(m.get("Artist", {}).get("value", "")) or limpio(m.get("Credit", {}).get("value", "")) or "Autor desconocido"
        out.append({"titulo": p["title"], "url": url, "pagina": ii.get("descriptionurl", ""),
                    "autor": autor[:120], "licencia": lic, "ancho": ii["width"], "alto": ii["height"],
                    "fuente": "Wikimedia Commons", "score": score})
    if not spec.startswith("File:"):
        out.sort(key=lambda c: -c["score"])
    return out


def candidatos_openverse(spec):
    try:
        r = get(OPENVERSE, params=dict(q=spec, license_type="commercial,modification", page_size=20, size="large"))
        res = r.json().get("results", []) if r.ok else []
    except Exception:
        return []
    out = []
    for x in res:
        lic = f"CC {x.get('license', '').upper()} {x.get('license_version') or ''}".strip()
        if x.get("license") in ("cc0", "pdm"):
            lic = "CC0" if x["license"] == "cc0" else "Public domain"
        out.append({"titulo": x.get("title") or spec, "url": x["url"], "pagina": x.get("foreign_landing_url", ""),
                    "autor": (x.get("creator") or "Autor desconocido")[:120], "licencia": lic,
                    "ancho": x.get("width") or 0, "alto": x.get("height") or 0, "fuente": x.get("provider", "Openverse")})
    return out


def descargar(c, path):
    for intento in range(3):
        r = get(c["url"])
        if r.ok and r.headers.get("content-type", "").startswith("image/"):
            break
        time.sleep(4 * (intento + 1))
    else:
        print(f"     (no se pudo descargar {c['titulo']}: HTTP {r.status_code})")
        return False
    tmp = path + ".part"
    open(tmp, "wb").write(r.content)
    try:
        im = ImageOps.exif_transpose(Image.open(tmp)).convert("RGB")
        if im.width < 900:
            raise ValueError("demasiado pequeña")
        im.save(path, quality=93)
    except Exception:
        os.remove(tmp)
        return False
    os.remove(tmp)
    return True


def contacto(gid, filas, path):
    tw, th, cols = 480, 270, 4
    rows = (len(filas) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + 40)), (20, 20, 24))
    d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype(C.F_BOLD, 18)
    for i, (etq, img, _) in enumerate(filas):
        x, y = (i % cols) * tw, (i // cols) * (th + 40)
        if img and os.path.exists(img):
            im = ImageOps.fit(Image.open(img).convert("RGB"), (tw - 6, th - 6))
            sheet.paste(im, (x + 3, y + 3))
        else:
            d.rectangle([x + 3, y + 3, x + tw - 3, y + th - 3], fill=(60, 30, 30))
        d.text((x + 6, y + th + 6), etq[:48], font=f, fill=(255, 255, 255))
    sheet.save(path, quality=85)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("guion", nargs="?")
    ap.add_argument("--buscar", help="lista candidatas de Commons para una búsqueda")
    ap.add_argument("--forzar", nargs="*", default=[], help="escenas (h3, s2...) cuya imagen hay que cambiar")
    a = ap.parse_args()
    if a.buscar:
        for c in candidatos_commons(a.buscar)[:15]:
            print(f"{c['titulo']}  [{c['ancho']}×{c['alto']}, {c['licencia']}]")
        return
    if not a.guion:
        ap.error("falta el guion")
    g = C.cargar_guion(a.guion)
    gid = g["_id"]
    idir = C.trabajo(gid, "img")
    cpath = os.path.join(idir, "creditos.json")
    cred = json.load(open(cpath, encoding="utf-8")) if os.path.exists(cpath) else {}
    descartes = cred.setdefault("_descartes", {})

    escenas = [(f"h{i}", sc) for i, sc in enumerate(g["escenas"])] + \
              [(f"s{i}", sc) for i, sc in enumerate(g.get("short", {}).get("escenas", []))]
    usados = {v["titulo"] for k, v in cred.items() if not k.startswith("_") and isinstance(v, dict)}
    for etq in a.forzar:
        sc = dict(escenas).get(etq)
        if sc and sc.get("imagen") in cred:
            descartes.setdefault(sc["imagen"], []).append(cred[sc["imagen"]]["titulo"])
            usados.discard(cred[sc["imagen"]]["titulo"])
            del cred[sc["imagen"]]

    filas = []
    for etq, sc in escenas:
        spec = (sc.get("imagen") or "").strip()
        if not spec or spec.startswith("@"):
            filas.append((f"{etq} · {spec or '(= anterior)'}", None, False))
            continue
        key = hashlib.sha1(spec.encode()).hexdigest()[:10]
        path = os.path.join(idir, key + ".jpg")
        if spec in cred and os.path.exists(path):
            filas.append((f"{etq} · {spec}", path, True))
            continue
        hecho = False
        for c in candidatos_commons(spec) + ([] if spec.startswith("File:") else candidatos_openverse(spec)):
            if c["titulo"] in usados or c["titulo"] in descartes.get(spec, []):
                continue
            if descargar(c, path):
                c["archivo"] = key + ".jpg"
                c.pop("score", None)
                cred[spec] = c
                usados.add(c["titulo"])
                hecho = True
                print(f"{etq:4} OK  {spec!r} -> {c['titulo']} ({c['licencia']})")
                break
            time.sleep(1)
        if not hecho:
            print(f"{etq:4} !!  {spec!r}: sin imagen válida; cambia la búsqueda")
        filas.append((f"{etq} · {spec}", path if hecho else None, True))
        json.dump(cred, open(cpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        time.sleep(1)

    json.dump(cred, open(cpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    cs = os.path.join(C.trabajo(gid), "contacto.jpg")
    contacto(gid, filas, cs)
    faltan = [e for e, p, req in filas if req and p is None]
    print(f"Hoja de contactos: {cs}" + (f"  ·  FALTAN {len(faltan)}" if faltan else ""))
    sys.exit(1 if faltan else 0)


if __name__ == "__main__":
    main()
