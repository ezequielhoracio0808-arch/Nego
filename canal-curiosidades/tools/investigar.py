#!/usr/bin/env python3
"""Busca qué vídeos de curiosidades en español están funcionando ahora mismo.

Uso:  python3 tools/investigar.py [--dias 14] [busqueda extra ...]
Salida: investigacion/AAAA-MM-DD.json y investigacion/AAAA-MM-DD.md

Usa la API de datos de YouTube (v3). La clave se toma de YOUTUBE_API_KEY o, si no existe,
la añade el proxy del entorno (secreto guardado para www.googleapis.com).
Si no hay acceso, escribe un informe que lo dice y termina con código 2: entonces
la investigación se hace con búsquedas web (ver DIARIO.md).
"""
import argparse, collections, datetime as dt, json, math, os, re, sys
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import CFG, ROOT

API = "https://www.googleapis.com/youtube/v3/"
KEY = os.environ.get("YOUTUBE_API_KEY", "")
STOP = set("""de la el en y a los las del un una que por con para es su al lo como más mas se no te tu
este esta esto son fue hay ya o sus pero qué que cómo como cuál quién por qué sobre entre sin muy
todo todos nadie nunca así the of and to in is you""".split())


def api(endpoint, **params):
    if KEY:
        params["key"] = KEY
    r = requests.get(API + endpoint, params=params, timeout=30)
    if r.status_code != 200:
        try:
            msg = r.json()["error"]["message"]
        except Exception:
            msg = r.text[:200]
        raise RuntimeError(f"{endpoint}: HTTP {r.status_code} — {msg}")
    return r.json()


def iso_dur(s):
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return 0
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


def fmt(n):
    n = float(n)
    for u, k in (("M", 1e6), ("K", 1e3)):
        if n >= k:
            return f"{n / k:.1f}{u}".replace(".0", "")
    return str(int(n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=CFG["investigacion"]["dias"])
    ap.add_argument("extra", nargs="*", help="búsquedas adicionales")
    a = ap.parse_args()

    hoy = dt.datetime.now(dt.timezone.utc)
    fecha = hoy.astimezone().strftime("%Y-%m-%d")
    os.makedirs(os.path.join(ROOT, "investigacion"), exist_ok=True)
    base = os.path.join(ROOT, "investigacion", fecha)
    desde = (hoy - dt.timedelta(days=a.dias)).strftime("%Y-%m-%dT%H:%M:%SZ")
    busquedas = CFG["investigacion"]["busquedas"] + a.extra

    try:
        ids, origen = [], collections.defaultdict(list)
        for q in busquedas:
            res = api("search", part="snippet", type="video", q=q, order="viewCount",
                      publishedAfter=desde, relevanceLanguage=CFG["investigacion"]["idioma"],
                      maxResults=CFG["investigacion"]["max_por_busqueda"], safeSearch="moderate")
            for it in res.get("items", []):
                vid = it["id"]["videoId"]
                if vid not in origen:
                    ids.append(vid)
                origen[vid].append(q)
        videos = []
        for i in range(0, len(ids), 50):
            res = api("videos", part="snippet,statistics,contentDetails", id=",".join(ids[i:i + 50]))
            videos += res.get("items", [])
        chans = {}
        cids = sorted({v["snippet"]["channelId"] for v in videos})
        for i in range(0, len(cids), 50):
            res = api("channels", part="statistics", id=",".join(cids[i:i + 50]))
            for c in res.get("items", []):
                chans[c["id"]] = int(c["statistics"].get("subscriberCount", 0) or 0)
    except Exception as e:  # sin clave, sin cuota o sin red
        with open(base + ".md", "w", encoding="utf-8") as f:
            f.write(f"# Investigación {fecha}\n\n**Sin acceso a la API de YouTube:** {e}\n\n"
                    "Haz la investigación con búsquedas web (ver DIARIO.md, paso 1-B).\n")
        print(f"SIN API DE YOUTUBE: {e}", file=sys.stderr)
        sys.exit(2)

    filas = []
    for v in videos:
        sn, st = v["snippet"], v.get("statistics", {})
        lang = (sn.get("defaultAudioLanguage") or sn.get("defaultLanguage") or "").lower()
        if lang and not lang.startswith("es"):
            continue
        views = int(st.get("viewCount", 0) or 0)
        pub = dt.datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00"))
        dias = max((hoy - pub).total_seconds() / 86400, 0.5)
        subs = chans.get(sn["channelId"], 0)
        dur = iso_dur(v["contentDetails"].get("duration"))
        vpd = views / dias
        ratio = views / max(subs, 1000)  # «outlier»: cuánto supera el vídeo al tamaño del canal
        filas.append({
            "id": v["id"], "url": f"https://youtu.be/{v['id']}", "titulo": sn["title"],
            "canal": sn["channelTitle"], "suscriptores": subs, "visitas": views,
            "likes": int(st.get("likeCount", 0) or 0), "comentarios": int(st.get("commentCount", 0) or 0),
            "dias": round(dias, 1), "visitas_dia": int(vpd), "ratio_canal": round(ratio, 2),
            "duracion_s": dur, "formato": "short" if dur <= 180 else "largo",
            "busquedas": origen[v["id"]],
            "puntuacion": round(math.log10(vpd + 1) + 0.6 * math.log10(ratio + 0.01), 3),
        })
    filas.sort(key=lambda r: -r["puntuacion"])
    largos = [r for r in filas if r["formato"] == "largo"]
    shorts = [r for r in filas if r["formato"] == "short"]

    palabras = collections.Counter()
    for r in filas[:40]:
        for w in re.findall(r"[a-záéíóúñü0-9]+", r["titulo"].lower()):
            if w not in STOP and len(w) > 2:
                palabras[w] += 1

    hist = []
    hp = os.path.join(ROOT, "historial.json")
    if os.path.exists(hp):
        hist = json.load(open(hp, encoding="utf-8"))

    json.dump({"fecha": fecha, "desde": desde, "busquedas": busquedas, "videos": filas},
              open(base + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    def tabla(rows, n):
        out = ["| # | Título | Canal (subs) | Visitas | Visitas/día | × canal | Dur. |", "|---|---|---|---|---|---|---|"]
        for i, r in enumerate(rows[:n], 1):
            t = r["titulo"].replace("|", "/")
            out.append(f"| {i} | [{t}]({r['url']}) | {r['canal']} ({fmt(r['suscriptores'])}) | {fmt(r['visitas'])} | "
                       f"{fmt(r['visitas_dia'])} | {r['ratio_canal']} | {r['duracion_s'] // 60}:{r['duracion_s'] % 60:02d} |")
        return "\n".join(out)

    md = [f"# Investigación {fecha}", "",
          f"Vídeos publicados en los últimos {a.dias} días · {len(filas)} vídeos analizados · "
          f"búsquedas: {', '.join(busquedas)}", "",
          "**Cómo leerlo:** *visitas/día* mide la velocidad; *× canal* = visitas ÷ suscriptores del canal. "
          "Un vídeo con × canal alto funcionó por el **tema y el título**, no por el tamaño del canal: "
          "son los mejores para inspirarse.", "",
          "## Vídeos largos que más funcionan", tabla(largos, 20), "",
          "## Shorts que más funcionan", tabla(shorts, 15), "",
          "## Palabras que más se repiten en los títulos top", ", ".join(f"{w} ({n})" for w, n in palabras.most_common(25)), "",
          "## Ya publicados en el canal (no repetir)",
          "\n".join(f"- {h['fecha']}: {h['titulo']}" for h in hist[-30:]) or "- (ninguno todavía)", ""]
    open(base + ".md", "w", encoding="utf-8").write("\n".join(md))
    print(f"OK {base}.md  ({len(largos)} largos, {len(shorts)} shorts)")


if __name__ == "__main__":
    main()
