"""Cartera de oportunidades de ingreso: ideas, su valor esperado y los resultados reales.

El ranking lo calcula el código (no el modelo) para que sea consistente:

    ganancia esperada = ingreso estimado × probabilidad − costo
    puntaje           = ganancia esperada ÷ horas de tu tiempo   (USD por hora tuya)

Cuando registras cuánto ganaste de verdad, se compara con lo estimado. Así el
agente ve si sus estimaciones son optimistas y qué tipo de ideas rinden.

Estados: idea → propuesta → en_marcha → ganada / fracasada  (o descartada).
El agente puede crear ideas, proponerlas, ajustarlas y descartarlas. Solo tú
puedes ponerlas en marcha ("aprobar") y registrar ganancias reales.
"""

from __future__ import annotations

import json
import re
import secrets

from .billetera import ahora
from .espacio import Espacio

ID_OP = re.compile(r"^op[0-9a-f]{4}$")
ACTIVAS = ("en_marcha", "propuesta", "idea")
CERRADAS = ("ganada", "fracasada", "descartada")
ESTADOS_DEL_AGENTE = ("idea", "propuesta", "descartada", "fracasada")
MAX_ACTIVAS = 30


def _ruta(esp: Espacio):
    return esp.dir / "oportunidades.json"


def cargar(esp: Espacio) -> list[dict]:
    ruta = _ruta(esp)
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else []


def guardar(esp: Espacio, lista: list[dict]) -> None:
    ruta = _ruta(esp)
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(lista, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(ruta)


def ganancia_esperada(op: dict) -> float:
    return op["ingreso_estimado_usd"] * op["probabilidad"] - op["costo_estimado_usd"]


def puntaje(op: dict) -> float:
    """USD de ganancia esperada por cada hora de tu tiempo."""
    return ganancia_esperada(op) / max(op["horas_tuyas"], 0.5)


def _buscar(lista: list[dict], id_: str) -> dict:
    for op in lista:
        if op["id"] == id_:
            return op
    raise KeyError(f"No hay ninguna oportunidad con id '{id_}'.")


def _nota(op: dict, texto: str, por: str) -> None:
    if texto:
        op.setdefault("notas", []).append(f"{ahora().strftime('%Y-%m-%d %H:%M')} ({por}): {texto}")


def _num(valor, nombre: str, minimo: float = 0.0, maximo: float | None = None) -> float:
    try:
        x = float(valor)
    except (TypeError, ValueError):
        raise ValueError(f"'{nombre}' debe ser un número.")
    if x < minimo or (maximo is not None and x > maximo):
        rango = f"entre {minimo} y {maximo}" if maximo is not None else f"mayor o igual a {minimo}"
        raise ValueError(f"'{nombre}' debe estar {rango}.")
    return x


def registrar(
    esp: Espacio,
    titulo: str,
    descripcion: str,
    categoria: str,
    ingreso_estimado_usd: float,
    probabilidad: float,
    costo_estimado_usd: float,
    horas_tuyas: float,
    primer_paso: str,
) -> dict:
    if not (titulo or "").strip():
        raise ValueError("La oportunidad necesita un título.")
    lista = cargar(esp)
    if sum(op["estado"] in ACTIVAS for op in lista) >= MAX_ACTIVAS:
        raise ValueError(f"Ya hay {MAX_ACTIVAS} oportunidades activas; descarta las peores antes de agregar más.")
    usados = {op["id"] for op in lista}
    id_ = "op" + secrets.token_hex(2)
    while id_ in usados:
        id_ = "op" + secrets.token_hex(2)
    marca = ahora().isoformat(timespec="seconds")
    op = {
        "id": id_,
        "titulo": titulo.strip(),
        "descripcion": descripcion.strip(),
        "categoria": (categoria or "otra").strip().lower(),
        "ingreso_estimado_usd": _num(ingreso_estimado_usd, "ingreso_estimado_usd"),
        "probabilidad": _num(probabilidad, "probabilidad", 0.0, 1.0),
        "costo_estimado_usd": _num(costo_estimado_usd, "costo_estimado_usd"),
        "horas_tuyas": _num(horas_tuyas, "horas_tuyas"),
        "primer_paso": primer_paso.strip(),
        "estado": "idea",
        "ingreso_real_usd": 0.0,
        "creada": marca,
        "actualizada": marca,
        "notas": [],
    }
    lista.append(op)
    guardar(esp, lista)
    esp.log(f"oportunidad {id_}: {op['titulo']} (puntaje {puntaje(op):.2f})")
    return op


def actualizar_por_agente(
    esp: Espacio,
    id_: str,
    estado: str,
    nota: str = "",
    probabilidad: float | None = None,
    ingreso_estimado_usd: float | None = None,
) -> dict:
    lista = cargar(esp)
    op = _buscar(lista, id_)
    if op["estado"] in CERRADAS:
        raise ValueError(f"La oportunidad {id_} ya está cerrada ({op['estado']}).")
    if estado and estado != "sin_cambio":
        if estado not in ESTADOS_DEL_AGENTE:
            raise ValueError("Solo tu humano puede ponerla en marcha o marcarla como ganada.")
        if op["estado"] == "en_marcha" and estado in ("idea", "propuesta"):
            raise ValueError("Ya está en marcha; no puedes volverla atrás.")
        op["estado"] = estado
    if probabilidad is not None:
        op["probabilidad"] = _num(probabilidad, "probabilidad", 0.0, 1.0)
    if ingreso_estimado_usd is not None:
        op["ingreso_estimado_usd"] = _num(ingreso_estimado_usd, "ingreso_estimado_usd")
    _nota(op, nota, "agente")
    op["actualizada"] = ahora().isoformat(timespec="seconds")
    guardar(esp, lista)
    return op


def decidir_humano(esp: Espacio, id_: str, aprobar: bool, razon: str = "") -> str:
    """Tú pones en marcha (aprobar) o descartas (rechazar) una oportunidad."""
    lista = cargar(esp)
    op = _buscar(lista, id_)
    if op["estado"] in CERRADAS:
        return f"La oportunidad {id_} ya estaba cerrada ({op['estado']})."
    op["estado"] = "en_marcha" if aprobar else "descartada"
    _nota(op, razon or ("puesta en marcha" if aprobar else "descartada"), "humano")
    op["actualizada"] = ahora().isoformat(timespec="seconds")
    guardar(esp, lista)
    if aprobar:
        aviso = (f"Tu humano puso EN MARCHA la oportunidad {id_} «{op['titulo']}». "
                 "Ayúdale a ejecutarla: siguientes pasos concretos, materiales, seguimiento.")
    else:
        aviso = f"Tu humano DESCARTÓ la oportunidad {id_} «{op['titulo']}». {razon}".strip()
    esp.dejar_en_bandeja("humano", aviso)
    return f"{'▶️ En marcha' if aprobar else '🗑 Descartada'}: [{id_}] {op['titulo']}"


def buscar_en_agentes(id_: str) -> Espacio:
    from .espacio import listar_agentes

    for n in listar_agentes():
        esp = Espacio(n)
        if any(op["id"] == id_ for op in cargar(esp)):
            return esp
    raise KeyError(f"No hay ninguna oportunidad con id '{id_}'.")


def registrar_ingreso(esp: Espacio, monto: float, id_: str | None = None, nota: str = "") -> str:
    """Registra dinero real que ganaste gracias al agente.

    Si indicas la oportunidad, queda como ganada y suma a sus resultados reales.
    El agente recibe en su billetera la comisión configurada (por defecto 10 %):
    así, si es útil, se financia solo, como en Automaton.
    """
    monto = _num(monto, "monto")
    if monto <= 0:
        raise ValueError("El monto debe ser mayor que 0.")
    titulo = ""
    if id_:
        lista = cargar(esp)
        op = _buscar(lista, id_)
        op["ingreso_real_usd"] = round(op.get("ingreso_real_usd", 0.0) + monto, 2)
        op["estado"] = "ganada"
        _nota(op, f"ingreso real ${monto:.2f}. {nota}".strip(), "humano")
        op["actualizada"] = ahora().isoformat(timespec="seconds")
        guardar(esp, lista)
        titulo = op["titulo"]
    with (esp.dir / "ingresos.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": ahora().isoformat(timespec="seconds"), "monto": monto,
                            "oportunidad": id_, "nota": nota}, ensure_ascii=False) + "\n")
    comision = round(monto * float(esp.config().get("comision_ingresos", 0.10)), 4)
    if comision > 0:
        esp.billetera().registrar("ingreso", comision, nota=f"comisión por ${monto:.2f} ganados", oportunidad=id_)
    origen = f" con [{id_}] «{titulo}»" if id_ else ""
    esp.dejar_en_bandeja(
        "humano",
        f"¡Gané ${monto:.2f} gracias a ti{origen}! {nota}".strip()
        + (f" Te asigné ${comision:.2f} de comisión para tu presupuesto." if comision > 0 else ""),
    )
    return f"💵 Ingreso de ${monto:.2f}{origen} registrado. Comisión para el agente: ${comision:.2f}."


def estadisticas(esp: Espacio) -> dict:
    lista = cargar(esp)
    ganadas = [op for op in lista if op["estado"] == "ganada"]
    estimado = sum(op["ingreso_estimado_usd"] for op in ganadas)
    real_ops = sum(op.get("ingreso_real_usd", 0.0) for op in ganadas)
    ruta = esp.dir / "ingresos.jsonl"
    total_real = 0.0
    if ruta.exists():
        total_real = sum(json.loads(l)["monto"] for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip())
    por_cat: dict[str, dict] = {}
    for op in lista:
        c = por_cat.setdefault(op["categoria"], {"ganadas": 0, "fracasadas": 0, "activas": 0, "real": 0.0})
        if op["estado"] == "ganada":
            c["ganadas"] += 1
            c["real"] += op.get("ingreso_real_usd", 0.0)
        elif op["estado"] == "fracasada":
            c["fracasadas"] += 1
        elif op["estado"] in ACTIVAS:
            c["activas"] += 1
    return {
        "total_real": round(total_real, 2),
        "calibracion": round(real_ops / estimado, 2) if estimado > 0 else None,
        "por_categoria": por_cat,
    }


def _linea(i: int, op: dict) -> str:
    return (
        f"{i}. [{op['id']}] {op['titulo']} — {op['categoria']} · {op['estado']}\n"
        f"   ganancia esperada ${ganancia_esperada(op):.0f} (ingreso ${op['ingreso_estimado_usd']:.0f} × "
        f"{op['probabilidad']:.0%} − costo ${op['costo_estimado_usd']:.0f}) · "
        f"${puntaje(op):.1f} por hora tuya ({op['horas_tuyas']:g} h)\n"
        f"   primer paso: {op['primer_paso']}"
    )


def activas_ordenadas(esp: Espacio) -> list[dict]:
    return sorted((op for op in cargar(esp) if op["estado"] in ACTIVAS), key=puntaje, reverse=True)


def ranking_texto(esp: Espacio, n: int = 10) -> str:
    activas = activas_ordenadas(esp)
    partes = []
    if activas:
        partes.append("Oportunidades activas, de más a menos rentable por hora de tu humano:")
        partes += [_linea(i, op) for i, op in enumerate(activas[:n], 1)]
        if len(activas) > n:
            partes.append(f"(y {len(activas) - n} más)")
    else:
        partes.append("No hay oportunidades activas todavía.")
    est = estadisticas(esp)
    partes.append("")
    partes.append(f"Resultados reales: ${est['total_real']:.2f} ganados en total.")
    if est["calibracion"] is not None:
        partes.append(
            f"Calibración: en las ganadas, lo real fue {est['calibracion']:.0%} de lo estimado"
            + (" → estás siendo optimista; estima más bajo." if est["calibracion"] < 0.8 else ".")
        )
    cats = [(c, d) for c, d in est["por_categoria"].items() if d["ganadas"] or d["fracasadas"]]
    if cats:
        partes.append("Por categoría (ganadas/fracasadas, ingreso real):")
        partes += [f"  - {c}: {d['ganadas']}/{d['fracasadas']}, ${d['real']:.0f}" for c, d in sorted(cats, key=lambda x: -x[1]["real"])]
    return "\n".join(partes)


def resumen_corto(esp: Espacio, n: int = 3) -> str:
    activas = activas_ordenadas(esp)
    if not activas:
        return "Oportunidades: ninguna activa todavía."
    top = "; ".join(f"[{op['id']}] {op['titulo']} ({op['estado']}, ${puntaje(op):.1f}/h)" for op in activas[:n])
    cuenta = {e: sum(op["estado"] == e for op in activas) for e in ACTIVAS}
    return (f"Oportunidades: {cuenta['en_marcha']} en marcha, {cuenta['propuesta']} propuestas, "
            f"{cuenta['idea']} ideas. Top: {top}")


def decidir(id_: str, aprobar: bool, razon: str = "") -> str:
    """Un solo verbo para todo: ids 'opXXXX' son oportunidades; el resto, acciones pendientes."""
    id_ = (id_ or "").strip().lower()
    if ID_OP.match(id_):
        return decidir_humano(buscar_en_agentes(id_), id_, aprobar, razon)
    from .acciones import resolver

    return resolver(id_, aprobar, razon)
