#!/usr/bin/env python3
"""Rendimiento de los vídeos publicados: guarda los datos de YouTube Analytics y compara qué funciona mejor.

Uso:
  python3 tools/rendimiento.py importar datos.json   # respuesta de vidiq_channel_analytics (dimensión video), guardada en un archivo
  python3 tools/rendimiento.py informe              # tabla por vídeo y comparación por rasgos (solo vídeos con 48 h o más)

Los datos se guardan en rendimiento.json: un registro por vídeo de YouTube con todas las mediciones (no se borra nada).
Los rasgos de cada vídeo (categoría, tipo de gancho, duración, hora...) salen de publicaciones.json y de su guion.
"""
import datetime as dt
import glob
import json
import os
import re
import statistics
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RJ = os.path.join(ROOT, "rendimiento.json")
PJ = os.path.join(ROOT, "publicaciones.json")
METRICAS = ["views", "engagedViews", "averageViewPercentage", "averageViewDuration", "likes", "comments", "shares",
            "subscribersGained", "estimatedMinutesWatched"]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⛩️]")


def yt_id(url):
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", url or "")
    return m.group(1) if m else None


def cargar(p, defecto):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else defecto


def filas(datos):
    """Admite varias formas de respuesta: {columnHeaders, rows}, {rows: [dict]}, [dict] o texto con un JSON dentro."""
    if isinstance(datos, str):
        m = re.search(r"[\[{].*[\]}]", datos, re.S)
        datos = json.loads(m.group(0)) if m else {}
    if isinstance(datos, dict):
        for k in ("data", "report", "result"):
            if isinstance(datos.get(k), (dict, list)) and not datos.get("rows"):
                return filas(datos[k])
        rows = datos.get("rows") or []
        heads = datos.get("columnHeaders") or datos.get("columns") or datos.get("headers")
        if heads and rows and isinstance(rows[0], list):
            nombres = [h.get("name") if isinstance(h, dict) else h for h in heads]
            return [dict(zip(nombres, r)) for r in rows]
        return [r for r in rows if isinstance(r, dict)]
    return [r for r in datos if isinstance(r, dict)] if isinstance(datos, list) else []


def guion_de(pid):
    for p in [f"guiones/shorts/{pid}.json", f"guiones/{pid}.json"]:
        p = os.path.join(ROOT, p)
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8"))
    return {}


def duracion(pid, formato):
    p = os.path.join(ROOT, "salida", pid, "short.mp4" if formato == "short" else "video.mp4")
    if not os.path.exists(p):
        return None
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                         capture_output=True, text=True).stdout.strip()
    return round(float(out), 1) if out else None


def rasgos(pub):
    g = guion_de(pub["id"])
    corto = pub.get("formato") == "short"
    esc = (g.get("short") or {}).get("escenas") if corto else g.get("escenas")
    gancho = (esc or [{}])[0].get("narracion", "")
    titulo = pub.get("titulo", "")
    hora = pub.get("publicar", "")[11:13]
    d = duracion(pub["id"], pub.get("formato"))
    return {
        "categoria": g.get("categoria") or ("actualidad" if "black-friday" in pub["id"] else "lugares"),
        "gancho": "pregunta" if gancho.strip().startswith("¿") else "afirmación",
        "gancho_texto": gancho[:90],
        "titulo_emoji": bool(EMOJI.search(titulo)),
        "titulo_prohibido": "PROHIBID" in titulo.upper(),
        "hora": hora or "?",
        "duracion_s": d,
        "tramo_duracion": None if d is None else ("<30 s" if d < 30 else "30-35 s" if d < 35 else ">=35 s") if corto else
                          ("<5 min" if d < 300 else ">=5 min"),
    }


def importar(archivo):
    datos = open(archivo, encoding="utf-8").read()
    try:
        datos = json.loads(datos)
    except ValueError:
        pass
    rs = filas(datos)
    pubs = {yt_id(p.get("url")): p for p in cargar(PJ, {}).get("publicaciones", []) if yt_id(p.get("url"))}
    reg = cargar(RJ, {"videos": {}})
    ahora = dt.datetime.now(dt.timezone.utc)
    n = 0
    for r in rs:
        vid = r.get("video") or r.get("videoId") or r.get("id")
        if not vid:
            continue
        v = reg["videos"].setdefault(vid, {"youtube": vid})
        p = pubs.get(vid)
        if p:
            v.update({"id": p["id"], "formato": p["formato"], "titulo": p["titulo"], "publicado": p["publicar"]})
            v["rasgos"] = rasgos(p)
        med = {"fecha": ahora.isoformat(timespec="minutes")}
        if v.get("publicado") and len(v["publicado"]) > 10:
            med["horas"] = round((ahora - dt.datetime.fromisoformat(v["publicado"])).total_seconds() / 3600)
        for m in METRICAS:
            if r.get(m) is not None:
                med[m] = r[m]
        v.setdefault("mediciones", []).append(med)
        n += 1
    json.dump(reg, open(RJ, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{n} vídeos actualizados en rendimiento.json")


def informe():
    reg = cargar(RJ, {"videos": {}})["videos"]
    vids = [v for v in reg.values() if v.get("mediciones")]
    if not vids:
        print("Todavía no hay datos. Importa primero la respuesta de vidiq_channel_analytics.")
        return
    for formato in ("short", "video"):
        grupo = [v for v in vids if v.get("formato") == formato]
        if not grupo:
            continue
        print(f"\n=== {formato.upper()}S ({len(grupo)})")
        print(f"{'visitas':>8} {'vis/h':>6} {'% visto':>8} {'likes':>5} {'subs':>4}  horas  título")
        for v in sorted(grupo, key=lambda v: -(v["mediciones"][-1].get("views") or 0)):
            m = v["mediciones"][-1]
            h = max(m.get("horas") or 1, 1)
            print(f"{m.get('views', 0):>8} {m.get('views', 0) / h:>6.1f} {m.get('averageViewPercentage', 0):>7.0f}% "
                  f"{m.get('likes', 0):>5} {m.get('subscribersGained', 0):>4}  {h:>5}  {v.get('titulo', v['youtube'])[:60]}")
        maduros = [v for v in grupo if (v["mediciones"][-1].get("horas") or 0) >= 48 and v.get("rasgos")]
        if len(maduros) < 4:
            print(f"(Comparación por rasgos: hace falta un mínimo de 4 {formato}s con 48 h o más; hay {len(maduros)}.)")
            continue
        print(f"\nComparación por rasgos ({len(maduros)} {formato}s con 48 h o más; mediana de visitas por hora y de % visto):")
        for clave in ("categoria", "gancho", "titulo_emoji", "titulo_prohibido", "hora", "tramo_duracion"):
            cubos = {}
            for v in maduros:
                cubos.setdefault(str(v["rasgos"].get(clave)), []).append(v)
            if len(cubos) < 2:
                continue
            print(f"  {clave}:")
            for k, vs in sorted(cubos.items()):
                vph = statistics.median((x["mediciones"][-1].get("views") or 0) / max(x["mediciones"][-1].get("horas") or 1, 1) for x in vs)
                ret = statistics.median(x["mediciones"][-1].get("averageViewPercentage") or 0 for x in vs)
                print(f"    {k:<12} n={len(vs):<3} visitas/h={vph:7.1f}  % visto={ret:5.0f}%")
        print("  Ojo: con pocos vídeos las diferencias pueden ser casualidad. Busca patrones que se repitan.")


if __name__ == "__main__":
    os.chdir(ROOT)
    if len(sys.argv) >= 3 and sys.argv[1] == "importar":
        importar(sys.argv[2])
    elif len(sys.argv) >= 2 and sys.argv[1] == "informe":
        informe()
    else:
        print(__doc__)
