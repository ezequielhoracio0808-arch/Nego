"""Acciones sensibles y el sistema de aprobaciones.

Todo lo que puede tener consecuencias fuera del agente (ejecutar comandos,
correr código que él mismo escribió, pagos, crear subagentes) pasa por aquí:
- En `chat` (estás presente) se te pregunta en el momento.
- En modo autónomo queda como "pendiente" hasta que lo apruebes con
  `python -m automaton aprobar <id>` (o /aprobar <id> por Telegram).
Al aprobar, la acción se ejecuta y el resultado llega a la bandeja del agente.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import subprocess
import sys

from .billetera import ahora, nivel
from .espacio import Espacio, NOMBRE_VALIDO, listar_agentes

LIMITE_SALIDA = 8000
NOMBRE_HABILIDAD = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
_SECRETO = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|PRIVATE)", re.I)


def recortar(texto: str, limite: int = LIMITE_SALIDA) -> str:
    texto = texto or ""
    if len(texto) <= limite:
        return texto
    mitad = limite // 2
    return texto[:mitad] + f"\n...[{len(texto) - limite} caracteres omitidos]...\n" + texto[-mitad:]


def entorno_seguro() -> dict:
    """Entorno para procesos hijos SIN tus claves (API key, tokens, contraseñas).

    Así el código que escribe el agente no puede leer ni filtrar tus secretos.
    """
    return {
        k: v
        for k, v in os.environ.items()
        if not _SECRETO.search(k) and not k.startswith(("ANTHROPIC_", "TELEGRAM_"))
    }


def _correr(args, esp: Espacio, cfg: dict, *, shell: bool, entrada: str | None = None) -> str:
    esp.workspace.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(
            args,
            shell=shell,
            cwd=esp.workspace,
            input=entrada,
            capture_output=True,
            text=True,
            timeout=cfg["timeout_comando_seg"],
            env=entorno_seguro(),
        )
    except subprocess.TimeoutExpired:
        return f"Error: se superó el tiempo límite de {cfg['timeout_comando_seg']} s."
    partes = [f"código de salida: {r.returncode}"]
    if r.stdout:
        partes.append("stdout:\n" + recortar(r.stdout))
    if r.stderr:
        partes.append("stderr:\n" + recortar(r.stderr))
    return "\n".join(partes)


# --- comandos -------------------------------------------------------------
def correr_comando(esp: Espacio, cfg: dict, comando: str) -> str:
    esp.log(f"$ {comando}")
    return _correr(comando, esp, cfg, shell=True)


# --- habilidades (herramientas que el agente se programa) -----------------
def _ruta_registro(esp: Espacio):
    return esp.habilidades / "registro.json"


def registro_habilidades(esp: Espacio) -> dict:
    ruta = _ruta_registro(esp)
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


def _guardar_registro(esp: Espacio, reg: dict) -> None:
    esp.habilidades.mkdir(parents=True, exist_ok=True)
    _ruta_registro(esp).write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")


def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def escribir_habilidad(esp: Espacio, nombre: str, descripcion: str, codigo: str, aprobada: bool) -> None:
    if not NOMBRE_HABILIDAD.match(nombre):
        raise ValueError("Nombre de habilidad inválido (minúsculas, números y _, 2 a 41 caracteres).")
    esp.habilidades.mkdir(parents=True, exist_ok=True)
    (esp.habilidades / f"{nombre}.py").write_text(codigo, encoding="utf-8")
    reg = registro_habilidades(esp)
    reg[nombre] = {
        "descripcion": descripcion,
        "sha256": _sha(codigo),
        "aprobada": bool(aprobada),
        "actualizada": ahora().isoformat(timespec="seconds"),
    }
    _guardar_registro(esp, reg)


def estado_habilidad(esp: Espacio, nombre: str) -> tuple[bool, str]:
    reg = registro_habilidades(esp)
    ruta = esp.habilidades / f"{nombre}.py"
    if nombre not in reg or not ruta.exists():
        return False, f"La habilidad '{nombre}' no existe."
    if _sha(ruta.read_text(encoding="utf-8")) != reg[nombre]["sha256"]:
        return False, f"El código de '{nombre}' cambió fuera del registro; necesita aprobarse de nuevo."
    if not reg[nombre]["aprobada"]:
        return False, f"La habilidad '{nombre}' todavía no fue aprobada por el humano."
    return True, "ok"


def aprobar_habilidad(esp: Espacio, nombre: str) -> str:
    reg = registro_habilidades(esp)
    ruta = esp.habilidades / f"{nombre}.py"
    if nombre not in reg or not ruta.exists():
        return f"La habilidad '{nombre}' no existe."
    reg[nombre]["aprobada"] = True
    reg[nombre]["sha256"] = _sha(ruta.read_text(encoding="utf-8"))
    _guardar_registro(esp, reg)
    return f"Habilidad '{nombre}' aprobada; ya puedes usarla con usar_habilidad."


def correr_habilidad(esp: Espacio, cfg: dict, nombre: str, entrada: str) -> str:
    ok, motivo = estado_habilidad(esp, nombre)
    if not ok:
        return "Error: " + motivo
    esp.log(f"habilidad {nombre} <- {recortar(entrada, 300)}")
    ruta = (esp.habilidades / f"{nombre}.py").resolve()
    return _correr([sys.executable, str(ruta)], esp, cfg, shell=False, entrada=entrada)


# --- pagos ----------------------------------------------------------------
def registrar_pago(esp: Espacio, monto: float, destinatario: str, concepto: str) -> str:
    esp.billetera().registrar("pago", monto, nota=concepto, destinatario=destinatario)
    return (
        f"Pago de ${monto:.2f} a {destinatario} ({concepto}) aprobado y descontado de la billetera. "
        "El humano se encarga de realizarlo."
    )


# --- subagentes -----------------------------------------------------------
def hijos_de(padre: str) -> list[str]:
    return [n for n in listar_agentes() if Espacio(n).config().get("padre") == padre]


def validar_subagente(padre: Espacio, nombre: str, presupuesto: float) -> str | None:
    cfg = padre.config()
    if cfg.get("es_subagente"):
        return "Un subagente no puede crear otros subagentes."
    if not NOMBRE_VALIDO.match(nombre or ""):
        return "Nombre inválido (minúsculas, números, - o _, de 2 a 32 caracteres)."
    if Espacio(nombre).existe():
        return f"Ya existe un agente llamado '{nombre}'."
    if len(hijos_de(padre.nombre)) >= cfg["max_subagentes"]:
        return f"Ya alcanzaste el máximo de {cfg['max_subagentes']} subagentes."
    if presupuesto <= 0:
        return "El presupuesto debe ser mayor que 0."
    saldo = padre.billetera().saldo()
    if presupuesto > saldo * 0.5:
        return f"Como máximo puedes ceder la mitad de tu saldo (${saldo * 0.5:.2f})."
    return None


def crear_subagente(padre: Espacio, nombre: str, mision: str, presupuesto: float) -> str:
    error = validar_subagente(padre, nombre, presupuesto)
    if error:
        return "Error: " + error
    cfg_padre = padre.config()
    hereda = {k: cfg_padre[k] for k in ("modelo", "esfuerzo", "comandos", "timeout_comando_seg",
                                       "habilidades_requieren_aprobacion", "web", "latido_minutos")}
    hijo = Espacio(nombre)
    hijo.crear(
        mision,
        {
            **hereda,
            "es_subagente": True,
            "padre": padre.nombre,
            "max_subagentes": 0,
            "rutinas": [],
            "max_gasto_diario_usd": min(cfg_padre["max_gasto_diario_usd"], presupuesto),
            "max_gasto_por_ciclo_usd": min(cfg_padre["max_gasto_por_ciclo_usd"], presupuesto),
            "umbral_ahorro_usd": min(cfg_padre["umbral_ahorro_usd"], presupuesto / 2),
            "umbral_critico_usd": min(cfg_padre["umbral_critico_usd"], presupuesto / 10),
        },
    )
    padre.billetera().registrar("transferencia_salida", presupuesto, nota=f"presupuesto para {nombre}")
    hijo.billetera().registrar("transferencia_entrada", presupuesto, nota=f"presupuesto inicial de {padre.nombre}")
    return f"Subagente '{nombre}' creado con ${presupuesto:.2f}. Se ejecutará en los próximos latidos."


# --- aprobaciones ---------------------------------------------------------
def describir(tipo: str, d: dict) -> str:
    if tipo == "comando":
        return f"Ejecutar comando: {d['comando']}"
    if tipo == "habilidad":
        return f"Aprobar habilidad '{d['nombre']}': {d.get('descripcion', '')}"
    if tipo == "pago":
        return f"Pago de ${d['monto_usd']:.2f} a {d['destinatario']} — {d['concepto']}"
    if tipo == "subagente":
        return f"Crear subagente '{d['nombre']}' con ${d['presupuesto_usd']:.2f} — misión: {d['mision']}"
    return f"{tipo}: {d}"


def ejecutar_aprobado(esp: Espacio, tipo: str, d: dict) -> str:
    cfg = esp.config()
    if tipo == "comando":
        return correr_comando(esp, cfg, d["comando"])
    if tipo == "habilidad":
        return aprobar_habilidad(esp, d["nombre"])
    if tipo == "pago":
        return registrar_pago(esp, float(d["monto_usd"]), d["destinatario"], d["concepto"])
    if tipo == "subagente":
        return crear_subagente(esp, d["nombre"], d["mision"], float(d["presupuesto_usd"]))
    return f"Error: tipo de acción desconocido '{tipo}'."


def solicitar(esp: Espacio, tipo: str, detalle: dict, motivo: str) -> dict:
    item = {
        "id": secrets.token_hex(3),
        "ts": ahora().isoformat(timespec="seconds"),
        "agente": esp.nombre,
        "tipo": tipo,
        "detalle": detalle,
        "motivo": motivo,
        "estado": "pendiente",
    }
    lista = esp.pendientes()
    lista.append(item)
    esp.guardar_pendientes(lista)
    esp.log(f"solicitud {item['id']}: {describir(tipo, detalle)}")
    return item


def todas_pendientes() -> list[dict]:
    salida = []
    for n in listar_agentes():
        salida += [p for p in Espacio(n).pendientes() if p["estado"] == "pendiente"]
    return salida


def _buscar(id_: str) -> tuple[Espacio, list[dict], dict]:
    for n in listar_agentes():
        esp = Espacio(n)
        lista = esp.pendientes()
        for item in lista:
            if item["id"] == id_:
                return esp, lista, item
    raise KeyError(f"No hay ninguna solicitud con id '{id_}'.")


def resolver(id_: str, aprobar: bool, razon: str = "") -> str:
    esp, lista, item = _buscar(id_)
    if item["estado"] != "pendiente":
        return f"La solicitud {id_} ya estaba {item['estado']}."
    if aprobar:
        resultado = ejecutar_aprobado(esp, item["tipo"], item["detalle"])
        item["estado"] = "ejecutado"
        item["resultado"] = recortar(resultado, 2000)
        aviso = f"Tu solicitud {id_} ({describir(item['tipo'], item['detalle'])}) fue APROBADA.\nResultado:\n{resultado}"
    else:
        resultado = f"Rechazada. {razon}".strip()
        item["estado"] = "rechazado"
        item["resultado"] = resultado
        aviso = f"Tu solicitud {id_} ({describir(item['tipo'], item['detalle'])}) fue RECHAZADA. {razon}".strip()
    item["resuelto"] = ahora().isoformat(timespec="seconds")
    esp.guardar_pendientes(lista)
    esp.dejar_en_bandeja("sistema", recortar(aviso, 4000))
    esp.log(f"solicitud {id_} -> {item['estado']}")
    return resultado


def resumen_estado(nombre: str) -> str:
    esp = Espacio(nombre)
    cfg = esp.config()
    b = esp.billetera()
    saldo = b.saldo()
    extra = " (PAUSADO)" if esp.pausado() else ""
    padre = f", hijo de {cfg['padre']}" if cfg.get("padre") else ""
    return (
        f"{nombre}{padre}{extra}: saldo ${saldo:.2f} · nivel {nivel(saldo, cfg)} · "
        f"gastado hoy ${b.consumido_hoy():.2f} de ${cfg['max_gasto_diario_usd']:.2f}"
    )
