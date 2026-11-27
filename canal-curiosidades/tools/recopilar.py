#!/usr/bin/env python3
"""Recopilación semanal: junta varios vídeos ya producidos en un solo guion largo (25–30 min).

Uso:
  python3 tools/recopilar.py receta.json

receta.json (lo escribe quien prepara la recopilación):
  {
    "id": "2026-12-06-recopilacion-lugares-prohibidos",    # nombre del guion nuevo (fecha de hoy + slug)
    "titulo": "...", "descripcion": "...", "miniatura": ["LÍNEA 1", "LÍNEA 2"],
    "titulo_pantalla": "LO MEJOR DE LA SEMANA",            # rótulo de la primera escena (≤ 28 caracteres)
    "intro": "narración de 2–3 frases que enganche y diga qué viene",
    "cierre": "narración final con pregunta y suscripción",
    "videos": ["2026-11-30-...", "2026-12-02-...", "2026-12-04-..."],  # ids de guiones/ (vídeos largos), en orden
    "miniatura_de": "2026-12-02-...",                      # opcional: de qué vídeo coger la foto de la miniatura
    "etiquetas": [...], "hashtags": [...]                   # opcionales
  }

Qué hace: copia las escenas de cada vídeo (sin su escena final de despedida), deja un capítulo por vídeo, junta
pronunciaciones y fuentes, y enlaza las fotos ya descargadas en trabajo/<id>/img con sus créditos. No descarga nada.
Después: python3 tools/producir.py <id> --solo video miniatura textos
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESPEDIDA = re.compile(r"suscr[ií]b|te leo en los comentarios", re.I)


def cargar(p):
    return json.load(open(p, encoding="utf-8"))


def main(receta):
    r = cargar(receta)
    nid = r["id"]
    dimg = os.path.join(ROOT, "trabajo", nid, "img")
    os.makedirs(dimg, exist_ok=True)
    cred, escenas, pron, fuentes, tags, vistas = {}, [], {}, [], [], set()

    def enlazar(src_dir, c):
        dst = os.path.join(dimg, c["archivo"])
        if not os.path.exists(dst):
            os.link(os.path.join(src_dir, c["archivo"]), dst)
        cred[c["titulo"]] = c
        return c["titulo"]

    fotos = {}  # id de vídeo -> foto de su miniatura
    for n, vid in enumerate(r["videos"], 1):
        g = cargar(os.path.join(ROOT, "guiones", vid + ".json"))
        sdir = os.path.join(ROOT, "trabajo", vid, "img")
        scred = cargar(os.path.join(sdir, "creditos.json"))
        pron.update(g.get("pron") or {})
        for f in g.get("fuentes", []):
            if isinstance(f, dict) and f["url"] not in vistas:
                vistas.add(f["url"])
                fuentes.append(f)
        tags += [t for t in g.get("etiquetas", [])[:4] if t not in tags]
        propias = [sc for sc in g["escenas"] if not DESPEDIDA.search(sc.get("narracion", ""))]
        last = None
        for k, sc in enumerate(g["escenas"]):
            spec = sc.get("imagen") or last
            last = spec
            if sc not in propias:
                continue
            c = scred.get(spec) if spec else None
            nueva = {"narracion": sc["narracion"]}
            if c:
                nueva["imagen"] = enlazar(sdir, c)
            if sc.get("cifra"):
                nueva["cifra"] = sc["cifra"]
            if sc.get("titulo"):
                nueva["titulo"] = sc["titulo"]
                nueva["capitulo"] = False  # los rótulos internos se ven, pero no son capítulos
            if not any(e.get("_video") == vid for e in escenas):  # primera escena del vídeo: capítulo
                nueva["capitulo"] = f"{n}. {re.sub(r'\s*[#|].*$', '', g['titulo']).strip()}"
                nueva.setdefault("titulo", (g.get("miniatura") or [g["titulo"]])[0][:28])
            nueva["_video"] = vid
            escenas.append(nueva)
        mi = g.get("miniatura_busqueda") or g["escenas"][g.get("miniatura_imagen", 0)].get("imagen")
        if mi in scred:
            fotos[vid] = enlazar(sdir, scred[mi])

    for e in escenas:
        e.pop("_video", None)
    primera = fotos.get(r.get("miniatura_de")) or next(iter(fotos.values()), escenas[0].get("imagen"))
    escenas.insert(0, {"titulo": r.get("titulo_pantalla", "LO MEJOR DE LA SEMANA")[:28], "capitulo": "Introducción",
                       "narracion": r["intro"], "imagen": primera})
    escenas.append({"titulo": "¿CUÁL TE HA GUSTADO MÁS?", "capitulo": "Final", "narracion": r["cierre"],
                    "imagen": escenas[-1].get("imagen")})
    guion = {
        "tema": f"Recopilación semanal: {', '.join(r['videos'])}",
        "por_que": "Recopilación de los vídeos de la semana con mejores visitas por hora; suma horas de visualización.",
        "categoria": "recopilación",
        "titulo": r["titulo"], "miniatura": r["miniatura"], "miniatura_busqueda": primera,
        "acento": r.get("acento", "#ffc22e"), "descripcion": r["descripcion"],
        "etiquetas": r.get("etiquetas") or tags[:12], "hashtags": r.get("hashtags") or ["curiosidades", "datoscuriosos", "recopilacion"],
        "pron": pron, "fuentes": fuentes, "escenas": escenas,
    }
    out = os.path.join(ROOT, "guiones", nid + ".json")
    json.dump(guion, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(cred, open(os.path.join(dimg, "creditos.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    palabras = sum(len(e["narracion"].split()) for e in escenas)
    print(f"Guion: {out}\n  {len(escenas)} escenas, {palabras} palabras (≈ {palabras / 180:.0f} min), "
          f"{len(cred)} fotos enlazadas, {len(fuentes)} fuentes")
    print(f"Siguiente paso: python3 tools/producir.py {nid} --solo video miniatura textos")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])
