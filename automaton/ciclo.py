"""Los modos de vida del agente: despertar (un ciclo), vivir (bucle) y chat."""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import anthropic

from . import oportunidades, telegram
from .acciones import registro_habilidades, resumen_estado, todas_pendientes
from .agente import Agente
from .avisos import avisar_humano
from .billetera import ahora, nivel
from .espacio import Espacio, home, listar_agentes

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _manejar_error_api(esp: Espacio, e: Exception) -> None:
    if isinstance(e, anthropic.AuthenticationError):
        msg = "No hay credenciales válidas de la API. Define ANTHROPIC_API_KEY (o usa `ant auth login`)."
    elif isinstance(e, anthropic.RateLimitError):
        msg = "Límite de uso de la API alcanzado; lo intentaré en el próximo latido."
    elif isinstance(e, anthropic.APIConnectionError):
        msg = "Sin conexión con la API; lo intentaré en el próximo latido."
    elif isinstance(e, anthropic.APIStatusError):
        msg = f"Error de la API ({e.status_code}): {e.message}"
    else:
        msg = f"Error inesperado: {e!r}"
    print(f"❌ [{esp.nombre}] {msg}")
    esp.log(f"error: {msg}")


def puede_trabajar(esp: Espacio) -> tuple[bool, str]:
    cfg = esp.config()
    if esp.pausado():
        return False, "pausado"
    b = esp.billetera()
    niv = nivel(b.saldo(), cfg)
    if niv in ("sin_fondos", "critico"):
        return False, niv
    if b.consumido_hoy() >= cfg["max_gasto_diario_usd"]:
        return False, "tope_diario"
    return True, niv


def _aviso_una_vez_al_dia(esp: Espacio, clave: str, texto: str) -> None:
    hoy = ahora().date().isoformat()
    if esp.estado().get(clave) != hoy:
        avisar_humano(esp, texto)
        esp.actualizar_estado(**{clave: hoy})


def _contexto_actual(esp: Espacio, encabezado: str, bandeja: list[dict]) -> str:
    cfg = esp.config()
    b = esp.billetera()
    saldo = b.saldo()
    t = ahora()
    est = esp.estado()
    lineas = [
        f"[{encabezado} · {DIAS[t.weekday()]} {t.strftime('%Y-%m-%d %H:%M')} (hora local)]",
        f"Billetera: saldo ${saldo:.2f} · nivel {nivel(saldo, cfg)} · gastado hoy ${b.consumido_hoy():.2f} "
        f"de ${cfg['max_gasto_diario_usd']:.2f} · tope por ciclo ${cfg['max_gasto_por_ciclo_usd']:.2f} "
        f"y {cfg['max_llamadas_por_ciclo']} llamadas.",
        f"Ciclos vividos: {est.get('ciclos', 0)}. Último despertar: {est.get('ultimo_despertar', 'nunca')}.",
        "",
    ]
    if bandeja:
        lineas.append(f"Bandeja ({len(bandeja)} mensajes nuevos):")
        lineas += [f"- [{m['ts']}] de {m['de']}: {m['texto']}" for m in bandeja]
    else:
        lineas.append("Bandeja: sin mensajes nuevos.")
    pend = [p for p in esp.pendientes() if p["estado"] == "pendiente"]
    lineas.append(
        "Tus solicitudes pendientes de aprobación: "
        + (", ".join(f"{p['id']} ({p['tipo']})" for p in pend) if pend else "ninguna")
    )
    lineas.append(oportunidades.resumen_corto(esp))
    reg = registro_habilidades(esp)
    if reg:
        lineas.append("Habilidades: " + ", ".join(f"{n}{'' if d['aprobada'] else ' (pendiente)'}" for n, d in sorted(reg.items())))
    notas = sorted(p.name for p in esp.memoria.glob("*.md"))
    lineas.append("Notas en memoria: " + (", ".join(notas) if notas else "ninguna (memoria vacía)"))
    return "\n".join(lineas)


def rutina_pendiente(esp: Espacio) -> dict | None:
    """La primera rutina de hoy cuya hora ya pasó y que todavía no se hizo."""
    t = ahora()
    est = esp.estado()
    hechas = est.get("rutinas_hechas", {})
    creado = datetime.fromisoformat(est["creado"]) if est.get("creado") else None
    for r in esp.config().get("rutinas", []):
        try:
            hh, mm = (int(x) for x in str(r["hora"]).split(":"))
            momento = t.replace(hour=hh, minute=mm, second=0, microsecond=0)
        except ValueError:
            esp.log(f"rutina con hora inválida: {r}")
            continue
        if r.get("dias") and DIAS[t.weekday()] not in r["dias"]:
            continue
        if t < momento or hechas.get(r["nombre"]) == t.date().isoformat():
            continue
        if creado and creado > momento:
            continue  # el día en que lo creas no corre lo que ya pasó
        return r
    return None


def despertar(esp: Espacio, cliente=None) -> str:
    """Ejecuta un ciclo autónomo (con la rutina del día si toca). Devuelve cómo terminó."""
    cfg = esp.config()
    ok, motivo = puede_trabajar(esp)
    proximo = ahora() + timedelta(minutes=cfg["latido_minutos"])
    if not ok:
        saldo = esp.billetera().saldo()
        if motivo == "critico":
            _aviso_una_vez_al_dia(
                esp, "aviso_critico",
                f"Me quedan ${saldo:.2f}. Estoy en nivel crítico y dejé de trabajar en modo autónomo. "
                f"Fondéame con: python -m automaton fondear 5 --agente {esp.nombre}",
            )
        elif motivo == "sin_fondos":
            _aviso_una_vez_al_dia(esp, "aviso_sin_fondos", "Me quedé sin fondos y estoy detenido.")
        elif motivo == "tope_diario":
            manana = (ahora() + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
            proximo = manana
        esp.actualizar_estado(proximo_despertar=proximo.isoformat(timespec="seconds"))
        esp.log(f"no despierto: {motivo}")
        print(f"💤 [{esp.nombre}] no trabaja ahora ({motivo.replace('_', ' ')}).")
        return motivo

    bandeja = esp.bandeja_sin_leer(marcar=False)
    n = esp.estado().get("ciclos", 0)
    mensaje = _contexto_actual(esp, "Despertar", bandeja)
    if n == 0:
        mensaje += (
            "\n\nEs tu PRIMER ciclo: lee tu identidad, define una estrategia inicial concreta con "
            "actualizar_identidad, crea tus notas de memoria y preséntate a tu humano con avisar_humano "
            "(qué harás y qué podrías necesitar de él)."
        )
    rutina = rutina_pendiente(esp)
    if rutina:
        mensaje += f"\n\n🗓 RUTINA DIARIA «{rutina['nombre']}» ({rutina['hora']}):\n{rutina['instruccion']}"
    elif n > 0:
        mensaje += (
            "\n\nDecide qué es lo más valioso que puedes hacer en este ciclo para tu misión. "
            "Si nada vale lo que cuesta, anota algo breve en tu memoria y duerme más tiempo."
        )

    print(f"\n🌅 [{esp.nombre}] despierta ({ahora().strftime('%H:%M')})" + (f" · rutina {rutina['nombre']}" if rutina else ""))
    esp.log("=== despertar ===" + (f" rutina {rutina['nombre']}" if rutina else ""))
    agente = Agente(esp, cliente, confirmar=None, autonomo=True)
    resultado = "ok"
    try:
        agente.turno(mensaje)
    except anthropic.APIError as e:
        _manejar_error_api(esp, e)
        resultado = "error"
    if resultado == "ok":
        esp.bandeja_sin_leer(marcar=True)
        if rutina:
            hechas = esp.estado().get("rutinas_hechas", {})
            hechas[rutina["nombre"]] = ahora().date().isoformat()
            esp.actualizar_estado(rutinas_hechas=hechas)
    if agente.ctx.dormir_minutos:
        proximo = ahora() + timedelta(minutes=agente.ctx.dormir_minutos)
    esp.actualizar_estado(
        ciclos=n + (1 if resultado == "ok" else 0),
        ultimo_despertar=ahora().isoformat(timespec="seconds"),
        proximo_despertar=proximo.isoformat(timespec="seconds"),
    )
    print(f"😴 [{esp.nombre}] duerme hasta {proximo.strftime('%H:%M')} · ciclo costó ${agente.gasto_total:.4f}")
    esp.log(f"=== fin del ciclo: ${agente.gasto_total:.4f}; próximo {proximo.isoformat(timespec='minutes')} ===")
    return resultado


def toca_despertar(esp: Espacio) -> bool:
    ok, _ = puede_trabajar(esp)
    proximo = esp.estado().get("proximo_despertar")
    if not proximo or datetime.fromisoformat(proximo) <= ahora():
        return True  # despertar() decide si trabaja o solo avisa
    # Despierta antes si toca una rutina o si le escribiste (solo si puede trabajar).
    if not ok:
        return False
    return rutina_pendiente(esp) is not None or any(
        m["de"] == "humano" for m in esp.bandeja_sin_leer(marcar=False)
    )


# --- control remoto (Telegram) ---------------------------------------------
def comando_remoto(texto: str, principal: str) -> str:
    partes = texto.strip().split()
    cmd = partes[0].lower() if partes else ""
    try:
        if cmd == "/estado":
            return "\n".join(resumen_estado(n) for n in listar_agentes()) or "No hay agentes."
        if cmd == "/pendientes":
            pend = todas_pendientes()
            if not pend:
                return "No hay nada pendiente."
            from .acciones import describir
            return "\n\n".join(f"[{p['id']}] {p['agente']}: {describir(p['tipo'], p['detalle'])}" for p in pend)
        if cmd == "/aprobar" and len(partes) >= 2:
            return "Aprobado.\n" + oportunidades.decidir(partes[1], True)
        if cmd == "/rechazar" and len(partes) >= 2:
            return oportunidades.decidir(partes[1], False, " ".join(partes[2:]))
        if cmd == "/ideas":
            return oportunidades.ranking_texto(Espacio(principal))
        if cmd == "/ingreso" and len(partes) >= 2:
            monto = float(partes[1].replace(",", "."))
            resto = partes[2:]
            id_ = resto.pop(0) if resto and oportunidades.ID_OP.match(resto[0]) else None
            esp = oportunidades.buscar_en_agentes(id_) if id_ else Espacio(principal)
            return oportunidades.registrar_ingreso(esp, monto, id_, " ".join(resto))
        if cmd == "/fondear" and len(partes) >= 2:
            monto = float(partes[1].replace(",", "."))
            if monto <= 0:
                return "El monto debe ser mayor que 0."
            nombre = partes[2] if len(partes) >= 3 else principal
            if not Espacio(nombre).existe():
                return f"No existe el agente '{nombre}'."
            Espacio(nombre).billetera().registrar("fondeo", monto, nota="fondeo por Telegram")
            return resumen_estado(nombre)
        if cmd == "/pausa":
            (home() / "PAUSA_TODO").touch()
            return "⏸ Todos los agentes en pausa."
        if cmd == "/reanudar":
            (home() / "PAUSA_TODO").unlink(missing_ok=True)
            return "▶️ Agentes reanudados."
        if cmd.startswith("/"):
            return ("Comandos: /estado /ideas /pendientes /aprobar <id> /rechazar <id> "
                    "/ingreso <usd> [id] [nota] /fondear <usd> [agente] /pausa /reanudar")
        Espacio(principal).dejar_en_bandeja("humano", texto)
        return f"📨 Mensaje dejado en la bandeja de {principal}; lo leerá en su próximo despertar."
    except (KeyError, ValueError) as e:
        return f"Error: {e.args[0] if e.args else e}"


def latido(nombres: list[str] | None = None, cliente=None) -> None:
    """Una sola revisión: atiende Telegram y despierta a quien le toque.

    Es lo que ejecuta GitHub Actions cada hora (y `vivir` en bucle).
    """
    agentes = nombres or listar_agentes()
    principal = "principal" if "principal" in agentes or not agentes else agentes[0]
    for texto in telegram.recibir():
        telegram.enviar(comando_remoto(texto, principal))
    for n in agentes:
        esp = Espacio(n)
        if not esp.existe() or esp.pausado():
            continue
        if toca_despertar(esp):
            despertar(esp, cliente)


def vivir(nombres: list[str] | None = None, cliente=None, sondeo_seg: int = 30) -> None:
    """Bucle principal: despierta a cada agente cuando le toca. Ctrl+C para salir."""
    print("🫀 Automaton en marcha. Ctrl+C para detener.  (Interruptor general: python -m automaton pausar --todos)")
    if telegram.configurado():
        print("📱 Control por Telegram activo.")
    while True:
        latido(nombres, cliente)
        time.sleep(sondeo_seg)


# --- conversación ------------------------------------------------------------
def confirmar_por_consola(texto: str) -> bool:
    print("\n" + "─" * 60)
    print("🔐 El agente pide permiso para:\n")
    print(texto)
    print("─" * 60)
    try:
        r = input("¿Apruebas? [s/N] ").strip().lower()
    except EOFError:
        return False
    return r in ("s", "si", "sí", "y", "yes")


def chat(esp: Espacio, cliente=None) -> None:
    if esp.pausado():
        print("El agente está en pausa. Usa: python -m automaton reanudar")
        return
    saldo = esp.billetera().saldo()
    if saldo <= 0:
        print("El agente no tiene fondos. Usa: python -m automaton fondear 5")
        return
    agente = Agente(esp, cliente, confirmar=confirmar_por_consola, autonomo=False)
    print(f"💬 Conversando con {esp.nombre} · saldo ${saldo:.2f} · esfuerzo {agente.esfuerzo}. Escribe 'salir' para terminar.\n")
    primero = True
    while True:
        try:
            texto = input("tú> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not texto:
            continue
        if texto.lower() in ("salir", "exit", "quit"):
            break
        if primero:
            bandeja = esp.bandeja_sin_leer(marcar=True)
            texto = _contexto_actual(esp, "Conversación con tu humano", bandeja) + "\n\nTu humano dice:\n" + texto
            primero = False
        esp.log(f"humano: {texto}")
        try:
            agente.turno(texto)
        except anthropic.APIError as e:
            _manejar_error_api(esp, e)
        print()
    print(f"Conversación terminada. Costo total: ${agente.gasto_total:.4f}")
