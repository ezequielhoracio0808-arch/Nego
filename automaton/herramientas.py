"""Las herramientas del agente: definición (lo que ve el modelo) y ejecución.

La lista de herramientas es FIJA durante toda una conversación (cambiarla a
mitad invalida la caché y el razonamiento preservado). Por eso el agente no
"instala" herramientas nuevas en la API: las programa como *habilidades* y las
invoca con `usar_habilidad`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .acciones import (
    correr_comando,
    correr_habilidad,
    describir,
    ejecutar_aprobado,
    escribir_habilidad,
    recortar,
    registro_habilidades,
    solicitar,
    validar_subagente,
)
from . import oportunidades
from .avisos import avisar_humano
from .billetera import nivel
from .espacio import Espacio


@dataclass
class Contexto:
    esp: Espacio
    cfg: dict
    # Si estás presente (modo chat) se te pregunta en el momento; si es None,
    # las acciones sensibles quedan pendientes de aprobación.
    confirmar: Optional[Callable[[str], bool]] = None
    dormir_minutos: Optional[int] = None
    fin_ciclo: bool = False


class ErrorHerramienta(Exception):
    """Error que se devuelve al modelo como tool_result con is_error=True."""


def _obj(propiedades: dict) -> dict:
    return {
        "type": "object",
        "properties": propiedades,
        "required": list(propiedades),
        "additionalProperties": False,
    }


_S = {"type": "string"}

DEFINICIONES: list[dict] = [
    {
        "name": "consultar_billetera",
        "description": "Muestra tu saldo, tu nivel de supervivencia, lo gastado hoy y los últimos movimientos.",
        "input_schema": _obj({}),
    },
    {
        "name": "memoria_leer",
        "description": (
            "Lee tu memoria persistente (notas en markdown que sobreviven entre ciclos). "
            "Con nombre vacío lista todas las notas; con un nombre devuelve esa nota."
        ),
        "input_schema": _obj({"nombre": {**_S, "description": "Nombre de la nota, p. ej. 'ideas.md', o '' para listar."}}),
    },
    {
        "name": "memoria_escribir",
        "description": "Guarda o amplía una nota de tu memoria persistente.",
        "input_schema": _obj({
            "nombre": {**_S, "description": "Nombre de la nota, p. ej. 'ideas.md'."},
            "contenido": _S,
            "modo": {"type": "string", "enum": ["reemplazar", "agregar"]},
        }),
    },
    {
        "name": "archivo_leer",
        "description": "Lee un archivo de texto de tu carpeta de trabajo (workspace).",
        "input_schema": _obj({"ruta": {**_S, "description": "Ruta relativa dentro de tu workspace."}}),
    },
    {
        "name": "archivo_escribir",
        "description": "Crea o reemplaza un archivo de texto en tu carpeta de trabajo (workspace).",
        "input_schema": _obj({"ruta": _S, "contenido": _S}),
    },
    {
        "name": "archivo_listar",
        "description": "Lista el contenido de una carpeta de tu workspace ('.' para la raíz).",
        "input_schema": _obj({"ruta": _S}),
    },
    {
        "name": "ejecutar_comando",
        "description": (
            "Ejecuta un comando de terminal dentro de tu workspace. Según la configuración puede "
            "requerir aprobación del humano. Los secretos del entorno no están disponibles."
        ),
        "input_schema": _obj({
            "comando": _S,
            "motivo": {**_S, "description": "Para qué lo necesitas, en una frase."},
        }),
    },
    {
        "name": "crear_habilidad",
        "description": (
            "Programa una nueva herramienta para ti mismo (o reemplaza una existente) como un script "
            "de Python. El script recibe la entrada por stdin y debe imprimir el resultado por stdout; "
            "se ejecuta con tu workspace como carpeta actual. Puede necesitar aprobación antes de usarse."
        ),
        "input_schema": _obj({
            "nombre": {**_S, "description": "snake_case, p. ej. 'resumir_csv'."},
            "descripcion": _S,
            "codigo": {**_S, "description": "Código Python completo."},
        }),
    },
    {
        "name": "usar_habilidad",
        "description": "Ejecuta una de tus habilidades aprobadas, pasándole un texto (o JSON) por stdin.",
        "input_schema": _obj({"nombre": _S, "entrada": _S}),
    },
    {
        "name": "listar_habilidades",
        "description": "Lista tus habilidades, su descripción y si están aprobadas.",
        "input_schema": _obj({}),
    },
    {
        "name": "actualizar_identidad",
        "description": (
            "Reescribe tu documento de identidad (misión, estrategia actual, aprendizajes). "
            "Es la parte de ti que puedes modificar; entra en vigor en tu próximo ciclo. "
            "No puedes cambiar tu constitución ni el código del sistema."
        ),
        "input_schema": _obj({"contenido": {**_S, "description": "El documento completo en markdown."}}),
    },
    {
        "name": "oportunidades_ranking",
        "description": (
            "Muestra tus oportunidades de ingreso activas ordenadas por ganancia esperada por hora de tu "
            "humano, más los resultados reales: cuánto se ganó, la calibración de tus estimaciones y qué "
            "categorías rindieron."
        ),
        "input_schema": _obj({}),
    },
    {
        "name": "oportunidad_registrar",
        "description": (
            "Registra una oportunidad concreta de generar ingresos para tu humano. Estima con honestidad: "
            "tus estimaciones se comparan luego con lo que se gana de verdad. Los montos son en USD para "
            "el primer mes (o el pago único si es algo puntual)."
        ),
        "input_schema": _obj({
            "titulo": _S,
            "descripcion": {**_S, "description": "Qué es, por qué funcionaría y riesgos."},
            "categoria": {**_S, "description": "Una palabra o dos, p. ej. 'freelance', 'reventa', 'contenido', 'servicios'."},
            "ingreso_estimado_usd": {"type": "number"},
            "probabilidad": {"type": "number", "description": "Entre 0 y 1: probabilidad realista de lograrlo."},
            "costo_estimado_usd": {"type": "number", "description": "Dinero a invertir (0 si nada)."},
            "horas_tuyas": {"type": "number", "description": "Horas de trabajo de tu humano que requiere."},
            "primer_paso": {**_S, "description": "Una acción concreta que tu humano pueda hacer hoy."},
        }),
    },
    {
        "name": "oportunidad_actualizar",
        "description": (
            "Actualiza una oportunidad: cambia su estado (idea, propuesta, descartada, fracasada), agrega "
            "una nota o corrige la probabilidad o el ingreso estimado (null para no cambiarlos). Solo tu "
            "humano puede ponerla en marcha o registrar ganancias."
        ),
        "input_schema": _obj({
            "id": _S,
            "estado": {"type": "string", "enum": ["sin_cambio", "idea", "propuesta", "descartada", "fracasada"]},
            "nota": _S,
            "probabilidad": {"anyOf": [{"type": "number"}, {"type": "null"}]},
            "ingreso_estimado_usd": {"anyOf": [{"type": "number"}, {"type": "null"}]},
        }),
    },
    {
        "name": "solicitar_pago",
        "description": (
            "Pide al humano que realice un pago (por ejemplo, un servicio o una API). Siempre requiere "
            "su aprobación; si lo aprueba, se descuenta de tu billetera y él lo paga."
        ),
        "input_schema": _obj({
            "monto_usd": {"type": "number"},
            "destinatario": _S,
            "concepto": {**_S, "description": "Qué se compra y por qué vale la pena."},
        }),
    },
    {
        "name": "proponer_subagente",
        "description": (
            "Propone crear un subagente con una misión concreta y parte de tu presupuesto (como "
            "máximo la mitad de tu saldo). Siempre requiere aprobación del humano. Los subagentes "
            "no pueden crear otros subagentes."
        ),
        "input_schema": _obj({
            "nombre": {**_S, "description": "minúsculas, p. ej. 'investigador'."},
            "mision": _S,
            "presupuesto_usd": {"type": "number"},
        }),
    },
    {
        "name": "avisar_humano",
        "description": (
            "Envía un mensaje a tu humano (archivo, consola y Telegram si está configurado). Úsalo para "
            "resultados importantes, preguntas o propuestas; no para cosas triviales."
        ),
        "input_schema": _obj({"mensaje": _S}),
    },
    {
        "name": "dormir",
        "description": (
            "Termina este ciclo y elige en cuántos minutos volver a despertar (entre 5 y 1440). "
            "En modo autónomo es tu última acción del ciclo: guarda antes en memoria lo importante."
        ),
        "input_schema": _obj({"minutos": {"type": "integer"}, "motivo": _S}),
    },
]


def definiciones(cfg: dict) -> list[dict]:
    tools = [{**d, "strict": True} for d in DEFINICIONES]
    if cfg.get("web"):
        n = int(cfg.get("max_busquedas_por_llamada", 5))
        tools.append({"type": "web_search_20260209", "name": "web_search", "max_uses": n})
        tools.append({"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": n})
    return tools


# --- utilidades -----------------------------------------------------------
def ruta_segura(base: Path, ruta: str) -> Path:
    """Resuelve `ruta` dentro de `base` y rechaza cualquier intento de salir."""
    base = base.resolve()
    destino = (base / (ruta or ".")).resolve()
    if destino != base and base not in destino.parents:
        raise ErrorHerramienta("Esa ruta queda fuera de tu carpeta permitida.")
    return destino


_NOMBRE_NOTA = re.compile(r"^[\w\- .]{1,80}$")


def _ruta_nota(esp: Espacio, nombre: str) -> Path:
    nombre = (nombre or "").strip()
    if not _NOMBRE_NOTA.match(nombre):
        raise ErrorHerramienta("Nombre de nota inválido.")
    if not nombre.endswith(".md"):
        nombre += ".md"
    return ruta_segura(esp.memoria, nombre)


def _accion_sensible(ctx: Contexto, tipo: str, detalle: dict, motivo: str, vista: str = "") -> str:
    texto = describir(tipo, detalle)
    if motivo:
        texto += f"\nMotivo: {motivo}"
    if ctx.confirmar is not None:
        if ctx.confirmar(texto + (f"\n\n{vista}" if vista else "")):
            return ejecutar_aprobado(ctx.esp, tipo, detalle)
        return "El humano rechazó esta acción. No intentes conseguirlo por otra vía; pregúntale o sigue con otra cosa."
    item = solicitar(ctx.esp, tipo, detalle, motivo)
    avisar_humano(
        ctx.esp,
        f"Pendiente de aprobación [{item['id']}]: {texto}\n"
        f"Aprobar: python -m automaton aprobar {item['id']}  ·  "
        f"Rechazar: python -m automaton rechazar {item['id']}",
    )
    return (
        f"Solicitud enviada al humano (id {item['id']}). Queda pendiente: verás el resultado en tu "
        "bandeja en un próximo ciclo. No la reintentes; sigue con otra cosa o termina el ciclo."
    )


# --- ejecución ------------------------------------------------------------
def ejecutar(nombre: str, entrada: dict, ctx: Contexto) -> str:
    """Ejecuta una herramienta. Lanza ErrorHerramienta para errores recuperables."""
    esp, cfg = ctx.esp, ctx.cfg

    if nombre == "consultar_billetera":
        b = esp.billetera()
        saldo = b.saldo()
        ultimos = b.movimientos()[-10:]
        lineas = [
            f"Saldo: ${saldo:.4f}",
            f"Nivel: {nivel(saldo, cfg)}",
            f"Gastado hoy: ${b.consumido_hoy():.4f} de ${cfg['max_gasto_diario_usd']:.2f}",
            "Últimos movimientos:",
        ]
        lineas += [f"  {m['ts']}  {m['tipo']:<22} {m['monto']:+.4f}  {m.get('nota', '')}" for m in ultimos]
        return "\n".join(lineas)

    if nombre == "memoria_leer":
        if not (entrada.get("nombre") or "").strip():
            notas = sorted(esp.memoria.glob("*.md"))
            if not notas:
                return "Tu memoria está vacía."
            return "\n".join(
                f"- {p.name} ({p.stat().st_size} bytes): "
                f"{(p.read_text(encoding='utf-8').strip().splitlines() or [''])[0][:100]}"
                for p in notas
            )
        ruta = _ruta_nota(esp, entrada["nombre"])
        if not ruta.exists():
            raise ErrorHerramienta(f"No existe la nota {ruta.name}.")
        return recortar(ruta.read_text(encoding="utf-8"), 20000)

    if nombre == "memoria_escribir":
        ruta = _ruta_nota(esp, entrada["nombre"])
        ruta.parent.mkdir(parents=True, exist_ok=True)
        if entrada.get("modo") == "agregar" and ruta.exists():
            with ruta.open("a", encoding="utf-8") as f:
                f.write("\n" + entrada["contenido"])
        else:
            ruta.write_text(entrada["contenido"], encoding="utf-8")
        return f"Nota {ruta.name} guardada."

    if nombre == "archivo_leer":
        ruta = ruta_segura(esp.workspace, entrada["ruta"])
        if not ruta.is_file():
            raise ErrorHerramienta("Ese archivo no existe.")
        return recortar(ruta.read_text(encoding="utf-8", errors="replace"), 20000)

    if nombre == "archivo_escribir":
        ruta = ruta_segura(esp.workspace, entrada["ruta"])
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(entrada["contenido"], encoding="utf-8")
        return f"Archivo guardado ({len(entrada['contenido'])} caracteres)."

    if nombre == "archivo_listar":
        ruta = ruta_segura(esp.workspace, entrada.get("ruta") or ".")
        if not ruta.is_dir():
            raise ErrorHerramienta("Esa carpeta no existe.")
        items = sorted(ruta.iterdir())[:300]
        if not items:
            return "(carpeta vacía)"
        return "\n".join(f"{p.name}/" if p.is_dir() else f"{p.name} ({p.stat().st_size} bytes)" for p in items)

    if nombre == "ejecutar_comando":
        modo = cfg.get("comandos", "aprobar")
        if modo == "no":
            raise ErrorHerramienta("Los comandos de terminal están desactivados en tu configuración.")
        if modo == "libre":
            return correr_comando(esp, cfg, entrada["comando"])
        return _accion_sensible(ctx, "comando", {"comando": entrada["comando"]}, entrada.get("motivo", ""))

    if nombre == "crear_habilidad":
        requiere = bool(cfg.get("habilidades_requieren_aprobacion", True))
        try:
            escribir_habilidad(esp, entrada["nombre"], entrada["descripcion"], entrada["codigo"], aprobada=not requiere)
        except ValueError as e:
            raise ErrorHerramienta(str(e)) from e
        if not requiere:
            return f"Habilidad '{entrada['nombre']}' guardada y lista para usar."
        vista = "Código:\n" + recortar(entrada["codigo"], 4000)
        return _accion_sensible(
            ctx, "habilidad", {"nombre": entrada["nombre"], "descripcion": entrada["descripcion"]}, "", vista
        )

    if nombre == "usar_habilidad":
        resultado = correr_habilidad(esp, cfg, entrada["nombre"], entrada.get("entrada", ""))
        if resultado.startswith("Error: "):
            raise ErrorHerramienta(resultado[len("Error: "):])
        return resultado

    if nombre == "listar_habilidades":
        reg = registro_habilidades(esp)
        if not reg:
            return "Todavía no tienes habilidades. Crea una con crear_habilidad."
        return "\n".join(
            f"- {n}: {d['descripcion']} [{'aprobada' if d['aprobada'] else 'pendiente de aprobación'}]"
            for n, d in sorted(reg.items())
        )

    if nombre == "actualizar_identidad":
        contenido = entrada["contenido"].strip()
        if len(contenido) > 12000:
            raise ErrorHerramienta("Tu identidad debe ser concisa (máximo 12000 caracteres).")
        esp.guardar_identidad(contenido + "\n")
        esp.log("identidad actualizada")
        return "Identidad actualizada. Entrará en vigor en tu próximo ciclo."

    if nombre == "oportunidades_ranking":
        return oportunidades.ranking_texto(esp)

    if nombre == "oportunidad_registrar":
        try:
            op = oportunidades.registrar(
                esp,
                entrada["titulo"],
                entrada["descripcion"],
                entrada["categoria"],
                entrada["ingreso_estimado_usd"],
                entrada["probabilidad"],
                entrada["costo_estimado_usd"],
                entrada["horas_tuyas"],
                entrada["primer_paso"],
            )
        except ValueError as e:
            raise ErrorHerramienta(str(e)) from e
        return (f"Registrada [{op['id']}] «{op['titulo']}»: ganancia esperada "
                f"${oportunidades.ganancia_esperada(op):.2f}, ${oportunidades.puntaje(op):.2f} por hora de tu humano.")

    if nombre == "oportunidad_actualizar":
        try:
            op = oportunidades.actualizar_por_agente(
                esp,
                entrada["id"],
                entrada.get("estado", "sin_cambio"),
                entrada.get("nota", ""),
                entrada.get("probabilidad"),
                entrada.get("ingreso_estimado_usd"),
            )
        except (KeyError, ValueError) as e:
            raise ErrorHerramienta(e.args[0] if e.args else str(e)) from e
        return f"[{op['id']}] ahora está en estado '{op['estado']}' (${oportunidades.puntaje(op):.2f} por hora)."

    if nombre == "solicitar_pago":
        monto = float(entrada["monto_usd"])
        if monto <= 0:
            raise ErrorHerramienta("El monto debe ser mayor que 0.")
        if monto > esp.billetera().saldo():
            raise ErrorHerramienta("No tienes saldo suficiente para ese pago.")
        detalle = {"monto_usd": monto, "destinatario": entrada["destinatario"], "concepto": entrada["concepto"]}
        return _accion_sensible(ctx, "pago", detalle, "")

    if nombre == "proponer_subagente":
        presupuesto = float(entrada["presupuesto_usd"])
        error = validar_subagente(esp, entrada["nombre"], presupuesto)
        if error:
            raise ErrorHerramienta(error)
        detalle = {"nombre": entrada["nombre"], "mision": entrada["mision"], "presupuesto_usd": presupuesto}
        return _accion_sensible(ctx, "subagente", detalle, "")

    if nombre == "avisar_humano":
        avisar_humano(esp, entrada["mensaje"])
        return "Mensaje enviado."

    if nombre == "dormir":
        minutos = max(5, min(1440, int(entrada["minutos"])))
        ctx.dormir_minutos = minutos
        ctx.fin_ciclo = True
        esp.log(f"dormir {minutos} min: {entrada.get('motivo', '')}")
        return f"De acuerdo: despertarás en unos {minutos} minutos."

    raise ErrorHerramienta(f"Herramienta desconocida: {nombre}")


def ejecutar_seguro(nombre: str, entrada, ctx: Contexto) -> tuple[str, bool]:
    """Como `ejecutar`, pero nunca lanza: devuelve (texto, es_error)."""
    if not isinstance(entrada, dict):
        try:
            entrada = json.loads(entrada)
        except Exception:
            return "Entrada inválida: se esperaba un objeto JSON.", True
    try:
        return ejecutar(nombre, entrada, ctx), False
    except ErrorHerramienta as e:
        return f"Error: {e}", True
    except Exception as e:  # un fallo inesperado no debe tumbar al agente
        ctx.esp.log(f"excepción en {nombre}: {e!r}")
        return f"Error inesperado en {nombre}: {e}", True
