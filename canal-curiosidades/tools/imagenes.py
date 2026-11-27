#!/usr/bin/env python3
"""Descarga las imágenes de un guion desde Wikimedia Commons (y Openverse como reserva),
solo con licencias que permiten uso comercial y modificación, y guarda la atribución.

Uso:  python3 tools/imagenes.py <guion|fecha> [--forzar h3 s1 ...]
      python3 tools/imagenes.py --buscar "texto"     (lista candidatas de Commons sin descargar)
  El campo "imagen" de cada escena puede ser:
    "texto de búsqueda"          -> busca en Commons (mejor en inglés: hay muchas más fotos)
    "texto de búsqueda#2"        -> otra foto distinta de esa misma búsqueda (sin gastar otra petición)
    "File:Nombre exacto.jpg"     -> esa imagen concreta de Commons
    "@fondo"                     -> fondo oscuro de la marca (para cifras o frases a pantalla completa)
  --forzar 3 5   descarta la imagen elegida para esas escenas y prueba la siguiente candidata.
Salida: trabajo/<id>/img/  (imágenes + creditos.json) y trabajo/<id>/contacto.jpg para revisarlas.
"""
import argparse, functools, hashlib, html, itertools, json, os, re, sys, time
from urllib.parse import quote, unquote
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


def nombre_autor(s):
    """Solo el nombre: sin «- Wikimedia Commons - © …», enlaces, paréntesis ni letras que la fuente no tiene (chino, etc.)."""
    s = re.split(r"\s+[-–|/]\s+|\s*[©(\[]|https?://", limpio(s))[0]
    s = re.sub(r"\s+", " ", "".join(ch for ch in s if ord(ch) < 0x2000)).strip(" ,.;:")
    return s[:60] or "Autor desconocido"


API_BLOQUEADA = False  # si la API de Commons nos bloquea mucho rato, se usan sus páginas web normales


def get(url, **kw):
    """GET con espera si Wikimedia limita las peticiones (429): respeta Retry-After o espera 30, 60, 120… s."""
    global API_BLOQUEADA
    for i in range(5):
        r = S.get(url, timeout=60, **kw)
        if r.status_code != 429:
            return r
        espera = int(r.headers.get("Retry-After", "0") or 0) or 30 * 2 ** i
        if url == COMMONS and espera > 300:
            print(f"     (la API de Commons pide esperar {espera // 60} min: paso a sus páginas web)", flush=True)
            API_BLOQUEADA = True
            return r
        print(f"     (Wikimedia pide esperar: {espera}s)", flush=True)
        time.sleep(min(espera, 7200) + 2)  # respetar la espera completa: reintentar antes alarga el bloqueo
    return r


@functools.lru_cache(maxsize=None)
def _web_info(titulo):
    """Datos de un archivo leyendo su página de Commons (licencia, autor, tamaño y URL)."""
    r = get("https://commons.wikimedia.org/wiki/" + quote(titulo.replace(" ", "_")))
    time.sleep(3)
    if not r.ok:
        return None
    h = r.text.replace("&#95;", "_")
    lics = [limpio(x) for x in re.findall(r'class="licensetpl_short"[^>]*>(.*?)</span>', h, re.S)]
    lic = next((l for l in lics if licencia_ok(l)), None)
    url = re.search(r'href="(https://upload\.wikimedia\.org/wikipedia/commons/\w/\w\w/[^"?]+)[^"]*"[^>]*class="internal"', h) \
        or re.search(r'class="internal"[^>]*href="(https://upload\.wikimedia\.org/wikipedia/commons/\w/\w\w/[^"?]+)', h)
    dim = re.search(r'class="fileInfo"[^>]*>\(([\d,.]+) × ([\d,.]+)', h)
    if not (lic and url and dim) or not re.search(r"\.(jpe?g|png)$", url.group(1), re.I):
        return None
    aut = re.search(r'id="fileinfotpl_aut".*?</td>\s*<td[^>]*>(.*?)</td>', h, re.S)
    attr = re.search(r'class="licensetpl_attr"[^>]*>(.*?)</span>', h, re.S)
    autor = limpio(attr.group(1)) if attr and limpio(attr.group(1)) else limpio(aut.group(1)) if aut else ""
    w, hh = (int(re.sub(r"[,.]", "", x)) for x in dim.groups())
    info = {"url": url.group(1), "width": w}
    turl, _ = thumb(info)
    if not turl:
        return None
    return {"titulo": titulo, "url": turl, "pagina": "https://commons.wikimedia.org/wiki/" + quote(titulo.replace(" ", "_")),
            "autor": nombre_autor(autor), "licencia": lic, "ancho": w, "alto": hh, "fuente": "Wikimedia Commons"}


@functools.lru_cache(maxsize=None)
def _web_buscar(texto):
    """Búsqueda en la página normal de Commons; devuelve candidatas sin pedir aún su página (se piden al usarlas)."""
    r = get("https://commons.wikimedia.org/w/index.php", params={"search": f"{texto} filetype:bitmap", "title": "Special:Search",
                                                                "ns6": 1, "fulltext": 1, "limit": 20})
    time.sleep(3)
    if not r.ok:
        return []
    h = r.text
    out = []
    for blk in re.findall(r'<li class="mw-search-result.*?</li>', h, re.S):
        t = re.search(r'href="/wiki/(File:[^"#?]+)"', blk)
        d = re.search(r'\(([\d,.]+) × ([\d,.]+)', blk)
        if not (t and d):
            continue
        titulo = unquote(t.group(1)).replace("_", " ")
        w, hh = (int(re.sub(r"[,.]", "", x)) for x in d.groups())
        if w < 960 or not re.search(r"\.(jpe?g|png)$", titulo, re.I):
            continue
        ar = w / max(hh, 1)
        out.append((-(2 if 1.25 <= ar <= 2.1 else 1 if ar >= 1 else 0) - (1 if w >= 1920 else 0) + len(out) * 0.05, titulo))
    out.sort()
    return [t for _, t in out]


def candidatos_web(spec):
    """Generador de candidatas usando las páginas web de Commons (modo sin API)."""
    if spec.startswith("File:"):
        c = _web_info(spec)
        if c:
            yield c
        return
    for t in _web_buscar(spec):
        c = _web_info(t)
        if c:
            yield c


_INFO = {}  # caché en memoria: búsqueda o "File:..." -> candidatas


def precargar(titulos):
    """Pide de una vez (50 por petición) los datos de varios "File:..." para no gastar una petición por foto."""
    pend = sorted({t for t in titulos if t.startswith("File:") and t not in _INFO})
    if API_BLOQUEADA:
        return
    for i in range(0, len(pend), 50):
        lote = pend[i:i + 50]
        r = get(COMMONS, params=dict(action="query", format="json", prop="imageinfo", titles="|".join(lote),
                                     iiprop="url|size|mime|extmetadata",
                                     iiextmetadatafilter="LicenseShortName|Artist|Credit|UsageTerms"))
        if not r.ok:
            if API_BLOQUEADA:
                return
            continue
        q = r.json().get("query", {})
        alias = {n["to"]: n["from"] for n in q.get("normalized", [])}
        for pg in q.get("pages", {}).values():
            _INFO[alias.get(pg["title"], pg["title"])] = _paginas({"x": pg})
        for t in lote:
            _INFO.setdefault(t, [])


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
    if API_BLOQUEADA:
        return candidatos_web(spec)
    out = _commons(spec)
    if API_BLOQUEADA and not out:
        return candidatos_web(spec)
    words = spec.split()
    while not out and not spec.startswith("File:") and len(words) > 2:
        words = words[:-1]
        out = _commons(" ".join(words))
    return out


def _commons(spec):
    if spec in _INFO:
        return _INFO[spec]
    params = dict(action="query", format="json", prop="imageinfo", iiprop="url|size|mime|extmetadata",
                  iiextmetadatafilter="LicenseShortName|Artist|Credit|UsageTerms")
    if spec.startswith("File:"):
        params["titles"] = spec
    else:
        params.update(generator="search", gsrsearch=f"{spec} filetype:bitmap", gsrnamespace=6, gsrlimit=20)
    r = get(COMMONS, params=params)
    pages = r.json().get("query", {}).get("pages", {}) if r.ok else {}
    out = _paginas(pages)
    if not spec.startswith("File:"):
        out.sort(key=lambda c: -c["score"])
    if r.ok:
        _INFO[spec] = out
    return out


def _paginas(pages):
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
                    "autor": nombre_autor(autor), "licencia": lic, "ancho": ii["width"], "alto": ii["height"],
                    "fuente": "Wikimedia Commons", "score": score})
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
                    "autor": nombre_autor(x.get("creator")), "licencia": lic,
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
    ap.add_argument("guion", nargs="*", help="uno o varios guiones (o fechas)")
    ap.add_argument("--buscar", help="lista candidatas de Commons para una búsqueda")
    ap.add_argument("--forzar", nargs="*", default=[], help="escenas (h3, s2...) cuya imagen hay que cambiar")
    a = ap.parse_args()
    if a.buscar:
        for c in itertools.islice(candidatos_commons(a.buscar), 15):
            print(f"{c['titulo']}  [{c['ancho']}×{c['alto']}, {c['licencia']}]")
        return
    if not a.guion:
        ap.error("falta el guion")
    gs = [C.cargar_guion(x) for x in a.guion]
    precargar([sc.get("imagen") or "" for g in gs for sc in g.get("escenas", []) + g.get("short", {}).get("escenas", [])])
    fallos = sum(procesar(g, a.forzar) for g in gs)
    sys.exit(1 if fallos else 0)


def procesar(g, forzar):
    gid = g["_id"]
    idir = C.trabajo(gid, "img")
    cpath = os.path.join(idir, "creditos.json")
    cred = json.load(open(cpath, encoding="utf-8")) if os.path.exists(cpath) else {}
    descartes = cred.setdefault("_descartes", {})

    escenas = [(f"h{i}", sc) for i, sc in enumerate(g.get("escenas", []))] + \
              [(f"s{i}", sc) for i, sc in enumerate(g.get("short", {}).get("escenas", []))]
    usados = {v["titulo"] for k, v in cred.items() if not k.startswith("_") and isinstance(v, dict)}
    for etq in forzar:
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
        if spec in cred and os.path.exists(os.path.join(idir, cred[spec]["archivo"])):
            filas.append((f"{etq} · {spec}", os.path.join(idir, cred[spec]["archivo"]), True))
            continue
        ya = next((v for k, v in cred.items() if not k.startswith("_") and isinstance(v, dict) and v.get("titulo") == spec
                   and os.path.exists(os.path.join(idir, v["archivo"]))), None)
        if ya:  # ese archivo ya se descargó para otra escena: se reutiliza
            cred[spec] = dict(ya)
            filas.append((f"{etq} · {spec}", os.path.join(idir, ya["archivo"]), True))
            continue
        hecho = False
        busq = re.sub(r"#\d+$", "", spec)  # "texto#2": otra foto distinta de la misma búsqueda
        for c in itertools.chain(candidatos_commons(busq), [] if busq.startswith("File:") else candidatos_openverse(busq)):
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
            time.sleep(2)
        if not hecho:
            print(f"{etq:4} !!  {spec!r}: sin imagen válida; cambia la búsqueda")
        filas.append((f"{etq} · {spec}", path if hecho else None, True))
        json.dump(cred, open(cpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        time.sleep(2)

    json.dump(cred, open(cpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    cs = os.path.join(C.trabajo(gid), "contacto.jpg")
    contacto(gid, filas, cs)
    faltan = [e for e, p, req in filas if req and p is None]
    print(f"Hoja de contactos: {cs}" + (f"  ·  FALTAN {len(faltan)}" if faltan else ""))
    return len(faltan)


if __name__ == "__main__":
    main()
