"""Línea de comandos:  python -m automaton <comando> ...

Ejecuta `python -m automaton --help` para ver todos los comandos.
"""

from __future__ import annotations

import argparse
import sys

from .acciones import describir, registro_habilidades, resolver, resumen_estado, todas_pendientes
from .espacio import Espacio, home, listar_agentes


def _agente(nombre: str) -> Espacio:
    esp = Espacio(nombre)
    if not esp.existe():
        sys.exit(f"No existe el agente '{nombre}'. Créalo con: python -m automaton iniciar --nombre {nombre}")
    return esp


def cmd_iniciar(a):
    esp = Espacio(a.nombre)
    mision = a.mision or input("¿Cuál es la misión de tu agente? (qué quieres que haga por ti)\n> ").strip()
    if not mision:
        sys.exit("La misión no puede estar vacía.")
    esp.crear(mision)
    if a.fondos > 0:
        esp.billetera().registrar("fondeo", a.fondos, nota="fondos iniciales")
    print(f"✅ Agente '{a.nombre}' creado en {esp.dir}")
    print(f"   {resumen_estado(a.nombre)}")
    print("\nSiguientes pasos:")
    print("   python -m automaton chat          # habla con él")
    print("   python -m automaton despertar     # un ciclo autónomo")
    print("   python -m automaton vivir         # que viva solo, despertando cada cierto tiempo")


def cmd_estado(a):
    agentes = [a.agente] if a.agente else listar_agentes()
    if not agentes:
        print("No hay agentes todavía. Crea uno con: python -m automaton iniciar")
        return
    for n in agentes:
        esp = _agente(n)
        print(resumen_estado(n))
        est = esp.estado()
        print(f"   ciclos: {est.get('ciclos', 0)} · próximo despertar: {est.get('proximo_despertar', 'cuando ejecutes vivir/despertar')}")
        if a.movimientos:
            for m in esp.billetera().movimientos()[-a.movimientos:]:
                print(f"   {m['ts']}  {m['tipo']:<22} {m['monto']:+.4f}  {m.get('nota', '')}")
    pend = todas_pendientes()
    if pend:
        print(f"\n⏳ {len(pend)} acciones esperan tu aprobación (python -m automaton pendientes)")


def cmd_fondear(a):
    if a.monto <= 0:
        sys.exit("El monto debe ser mayor que 0.")
    esp = _agente(a.agente)
    esp.billetera().registrar("fondeo", a.monto, nota=a.nota or "fondeo manual")
    print(resumen_estado(a.agente))


def cmd_ingreso(a):
    if a.monto <= 0:
        sys.exit("El monto debe ser mayor que 0.")
    esp = _agente(a.agente)
    esp.billetera().registrar("ingreso", a.monto, nota=a.nota)
    esp.dejar_en_bandeja("humano", f"Registré un ingreso de ${a.monto:.2f} gracias a ti: {a.nota}")
    print(resumen_estado(a.agente))


def cmd_decir(a):
    esp = _agente(a.agente)
    esp.dejar_en_bandeja("humano", " ".join(a.mensaje))
    print(f"📨 Mensaje dejado en la bandeja de {a.agente}.")


def cmd_pendientes(a):
    pend = todas_pendientes()
    if not pend:
        print("No hay nada pendiente de aprobación.")
        return
    for p in pend:
        print(f"[{p['id']}] {p['agente']} · {p['ts']}")
        print(f"   {describir(p['tipo'], p['detalle'])}")
        if p.get("motivo"):
            print(f"   motivo: {p['motivo']}")
        if p["tipo"] == "habilidad":
            print(f"   revisa el código en: {Espacio(p['agente']).habilidades / (p['detalle']['nombre'] + '.py')}")
    print("\nAprobar: python -m automaton aprobar <id>   ·   Rechazar: python -m automaton rechazar <id>")


def cmd_aprobar(a):
    try:
        print(resolver(a.id, True))
    except KeyError as e:
        sys.exit(e.args[0])


def cmd_rechazar(a):
    try:
        print(resolver(a.id, False, a.razon or ""))
    except KeyError as e:
        sys.exit(e.args[0])


def cmd_pausar(a):
    if a.todos:
        home().mkdir(parents=True, exist_ok=True)
        (home() / "PAUSA_TODO").touch()
        print("⏸ Todos los agentes en pausa.")
    else:
        (_agente(a.agente).dir / "PAUSA").touch()
        print(f"⏸ {a.agente} en pausa.")


def cmd_reanudar(a):
    if a.todos:
        (home() / "PAUSA_TODO").unlink(missing_ok=True)
        print("▶️ Interruptor general desactivado.")
    else:
        (_agente(a.agente).dir / "PAUSA").unlink(missing_ok=True)
        print(f"▶️ {a.agente} reanudado.")


def cmd_habilidades(a):
    esp = _agente(a.agente)
    reg = registro_habilidades(esp)
    if not reg:
        print("Este agente todavía no se programó ninguna habilidad.")
    for n, d in sorted(reg.items()):
        print(f"- {n}: {d['descripcion']} [{'aprobada' if d['aprobada'] else 'pendiente'}]")


def cmd_chat(a):
    from .ciclo import chat
    chat(_agente(a.agente))


def cmd_despertar(a):
    from .ciclo import despertar
    despertar(_agente(a.agente))


def cmd_vivir(a):
    from .ciclo import vivir
    nombres = None if a.todos else [a.agente]
    if nombres:
        _agente(a.agente)
    try:
        vivir(nombres, sondeo_seg=a.sondeo)
    except KeyboardInterrupt:
        print("\n👋 Detenido.")


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m automaton", description="Tu agente autónomo personal.")
    sub = p.add_subparsers(dest="comando", required=True)

    def con_agente(sp):
        sp.add_argument("--agente", default="principal", help="nombre del agente (por defecto: principal)")
        return sp

    s = sub.add_parser("iniciar", help="crea un agente nuevo")
    s.add_argument("--nombre", default="principal")
    s.add_argument("--mision", default="")
    s.add_argument("--fondos", type=float, default=5.0, help="presupuesto inicial en USD (por defecto 5)")
    s.set_defaults(f=cmd_iniciar)

    s = sub.add_parser("estado", help="saldo, nivel y actividad")
    s.add_argument("--agente", default=None)
    s.add_argument("--movimientos", type=int, default=0, help="mostrar los últimos N movimientos")
    s.set_defaults(f=cmd_estado)

    s = con_agente(sub.add_parser("chat", help="conversa con el agente (te pide permiso en el momento)"))
    s.set_defaults(f=cmd_chat)

    s = con_agente(sub.add_parser("despertar", help="ejecuta un solo ciclo autónomo"))
    s.set_defaults(f=cmd_despertar)

    s = con_agente(sub.add_parser("vivir", help="bucle autónomo: despierta en cada latido"))
    s.add_argument("--todos", action="store_true", help="incluye a todos los agentes y subagentes")
    s.add_argument("--sondeo", type=int, default=30, help="segundos entre revisiones")
    s.set_defaults(f=cmd_vivir)

    s = con_agente(sub.add_parser("fondear", help="agrega presupuesto a la billetera"))
    s.add_argument("monto", type=float)
    s.add_argument("--nota", default="")
    s.set_defaults(f=cmd_fondear)

    s = con_agente(sub.add_parser("ingreso", help="registra dinero que el agente ayudó a ganar"))
    s.add_argument("monto", type=float)
    s.add_argument("nota")
    s.set_defaults(f=cmd_ingreso)

    s = con_agente(sub.add_parser("decir", help="deja un mensaje en la bandeja del agente"))
    s.add_argument("mensaje", nargs="+")
    s.set_defaults(f=cmd_decir)

    sub.add_parser("pendientes", help="acciones que esperan tu aprobación").set_defaults(f=cmd_pendientes)

    s = sub.add_parser("aprobar", help="aprueba (y ejecuta) una acción pendiente")
    s.add_argument("id")
    s.set_defaults(f=cmd_aprobar)

    s = sub.add_parser("rechazar", help="rechaza una acción pendiente")
    s.add_argument("id")
    s.add_argument("--razon", default="")
    s.set_defaults(f=cmd_rechazar)

    s = con_agente(sub.add_parser("pausar", help="pausa un agente (o --todos)"))
    s.add_argument("--todos", action="store_true")
    s.set_defaults(f=cmd_pausar)

    s = con_agente(sub.add_parser("reanudar", help="quita la pausa"))
    s.add_argument("--todos", action="store_true")
    s.set_defaults(f=cmd_reanudar)

    s = con_agente(sub.add_parser("habilidades", help="lista las habilidades que el agente se programó"))
    s.set_defaults(f=cmd_habilidades)

    a = p.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    main()
