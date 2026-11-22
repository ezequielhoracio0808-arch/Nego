"""El bucle del agente: llama a Claude, ejecuta herramientas y lleva la cuenta del gasto.

Claves de diseño:
- Antes de CADA llamada se verifica el presupuesto (saldo, tope diario, tope por
  ciclo, número de llamadas, pausa). Si algo falla, el agente se frena.
- Después de cada llamada se descuenta el costo real (según los tokens usados).
- El historial es de solo anexado y `system`/`tools` no cambian durante una
  conversación: así funcionan la caché y el razonamiento preservado del modelo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable, Optional

import anthropic

from .acciones import recortar
from .billetera import nivel
from .espacio import Espacio
from .herramientas import Contexto, definiciones, ejecutar_seguro
from .precios import costo_respuesta

CONSTITUCION = (Path(__file__).parent / "constitucion.md").read_text(encoding="utf-8")

# Respaldo del lado del servidor: si el modelo declina por política (p. ej. un
# falso positivo de los clasificadores), la API reintenta con otro modelo en la
# misma llamada en lugar de dejar al agente parado.
BETAS = ["server-side-fallback-2026-07-01"]

_TTY = sys.stdout.isatty()


def _tenue(texto: str) -> str:
    return f"\033[2m{texto}\033[0m" if _TTY else texto


class Freno(Exception):
    """El agente debe detenerse (presupuesto, pausa o límite de llamadas)."""


def limpiar_tras_respaldo(contenido: list) -> list:
    """Prepara el contenido para devolverlo a la API después de un respaldo.

    Si la respuesta trae un bloque `fallback`, antes de ese límite se omiten los
    bloques internos del modelo que declinó (thinking, tool_use sin ejecutar y
    tipos desconocidos); se conservan el texto y los pares completos de
    herramientas del servidor. Lo que viene después del límite se queda igual.
    """
    indices = [i for i, b in enumerate(contenido) if getattr(b, "type", None) == "fallback"]
    if not indices:
        return list(contenido)
    limite = indices[-1]
    antes = contenido[:limite]
    con_resultado = {
        getattr(b, "tool_use_id", None)
        for b in antes
        if getattr(b, "type", "").endswith("_tool_result") and b.type != "tool_result"
    }
    conservar = []
    for b in antes:
        t = getattr(b, "type", "")
        if t in ("text", "fallback"):
            conservar.append(b)
        elif t == "server_tool_use" and getattr(b, "id", None) in con_resultado:
            conservar.append(b)
        elif t.endswith("_tool_result") and t != "tool_result":
            conservar.append(b)
    return conservar + list(contenido[limite:])


class Agente:
    def __init__(
        self,
        esp: Espacio,
        cliente=None,
        confirmar: Optional[Callable[[str], bool]] = None,
        autonomo: bool = False,
        salida: Callable[[str], None] = print,
    ):
        self.esp = esp
        self.cfg = esp.config()
        self.cliente = cliente if cliente is not None else anthropic.Anthropic()
        self.ctx = Contexto(esp, self.cfg, confirmar)
        self.autonomo = autonomo
        self.salida = salida

        saldo = esp.billetera().saldo()
        self.nivel_inicial = nivel(saldo, self.cfg)
        self.modelo = self.cfg["modelo"]
        self.esfuerzo = self.cfg["esfuerzo"].get(self.nivel_inicial, "low")

        # Fijos durante toda la conversación (byte a byte).
        rol = f"Te llamas **{esp.nombre}**."
        if self.cfg.get("es_subagente"):
            rol += f" Eres un subagente creado por **{self.cfg.get('padre')}**; tu presupuesto es limitado y no puedes crear subagentes."
        self.system = [
            {"type": "text", "text": CONSTITUCION, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": f"# Tu identidad (la escribes tú)\n\n{rol}\n\n{esp.identidad()}"},
        ]
        self.tools = definiciones(self.cfg)
        self.mensajes: list[dict] = []
        self.gasto_turno = 0.0
        self.llamadas_turno = 0
        self.gasto_total = 0.0

    # --- presupuesto --------------------------------------------------------
    def _verificar(self) -> None:
        if self.esp.pausado():
            raise Freno("El agente está en pausa.")
        b = self.esp.billetera()
        if b.saldo() <= 0:
            raise Freno("Sin fondos en la billetera.")
        if b.consumido_hoy() >= self.cfg["max_gasto_diario_usd"]:
            raise Freno(f"Se alcanzó el tope diario de ${self.cfg['max_gasto_diario_usd']:.2f}.")
        if self.gasto_turno >= self.cfg["max_gasto_por_ciclo_usd"]:
            raise Freno(f"Se alcanzó el tope por ciclo de ${self.cfg['max_gasto_por_ciclo_usd']:.2f}.")
        if self.llamadas_turno >= self.cfg["max_llamadas_por_ciclo"]:
            raise Freno(f"Se alcanzó el máximo de {self.cfg['max_llamadas_por_ciclo']} llamadas por ciclo.")

    def _llamar(self):
        self._verificar()
        resp = self.cliente.beta.messages.create(
            model=self.modelo,
            max_tokens=self.cfg["max_tokens"],
            system=self.system,
            tools=self.tools,
            messages=self.mensajes,
            thinking={"type": "adaptive", "display": "summarized"},
            output_config={"effort": self.esfuerzo},
            cache_control={"type": "ephemeral"},
            betas=BETAS,
            fallbacks="default",
        )
        costo = costo_respuesta(resp, self.modelo)
        uso = resp.usage
        self.esp.billetera().registrar(
            "gasto",
            costo,
            nota="llamada al modelo",
            modelo=getattr(resp, "model", self.modelo),
            entrada=getattr(uso, "input_tokens", 0),
            salida=getattr(uso, "output_tokens", 0),
            cache_lectura=getattr(uso, "cache_read_input_tokens", 0) or 0,
        )
        self.gasto_turno += costo
        self.gasto_total += costo
        self.llamadas_turno += 1
        return resp, costo

    # --- presentación -------------------------------------------------------
    def _mostrar(self, contenido: list, costo: float) -> None:
        for b in contenido:
            t = getattr(b, "type", "")
            if t == "thinking" and getattr(b, "thinking", ""):
                self.salida(_tenue("💭 " + b.thinking.strip()))
            elif t == "text" and b.text.strip():
                self.salida(b.text.strip())
                self.esp.log(f"agente: {b.text.strip()}")
            elif t == "tool_use":
                args = recortar(json.dumps(b.input, ensure_ascii=False), 300)
                self.salida(_tenue(f"🔧 {b.name} {args}"))
                self.esp.log(f"herramienta {b.name} {args}")
            elif t == "server_tool_use":
                args = recortar(json.dumps(getattr(b, "input", {}), ensure_ascii=False), 200)
                self.salida(_tenue(f"🌐 {b.name} {args}"))
                self.esp.log(f"web {b.name} {args}")
            elif t == "fallback":
                self.salida(_tenue(f"↪ respondió el modelo de respaldo {b.to.model}"))
        self.salida(_tenue(f"   (costo ${costo:.4f} · saldo ${self.esp.billetera().saldo():.4f})"))

    # --- bucle ----------------------------------------------------------------
    def turno(self, contenido_usuario) -> str:
        """Agrega un mensaje de usuario y trabaja hasta que el modelo termine o se frene."""
        self.mensajes.append({"role": "user", "content": contenido_usuario})
        self.gasto_turno = 0.0
        self.llamadas_turno = 0
        ultimo_texto = ""
        while True:
            try:
                resp, costo = self._llamar()
            except Freno as f:
                self.salida(f"⛔ {f}")
                self.esp.log(f"freno: {f}")
                return ultimo_texto

            contenido = limpiar_tras_respaldo(list(resp.content))
            self._mostrar(contenido, costo)
            textos = [b.text for b in contenido if getattr(b, "type", "") == "text" and b.text.strip()]
            if textos:
                ultimo_texto = "\n".join(textos)

            if resp.stop_reason == "refusal":
                detalle = getattr(resp, "stop_details", None)
                categoria = getattr(detalle, "category", None) if detalle else None
                self.salida(f"⚠️  El modelo declinó esta petición (categoría: {categoria}).")
                self.esp.log(f"rechazo del modelo: {categoria}")
                return ultimo_texto
            if resp.stop_reason == "max_tokens":
                self.salida("⚠️  La respuesta se cortó por el límite de tokens; termino este turno.")
                self.esp.log("respuesta cortada por max_tokens")
                return ultimo_texto

            self.mensajes.append({"role": "assistant", "content": contenido})

            if resp.stop_reason == "pause_turn":
                continue  # una herramienta del servidor pausó: se reanuda reenviando

            usos = [b for b in contenido if getattr(b, "type", "") == "tool_use"]
            if not usos:
                return ultimo_texto

            resultados = []
            for u in usos:
                texto, es_error = ejecutar_seguro(u.name, u.input, self.ctx)
                self.salida(_tenue(("   ✗ " if es_error else "   ↳ ") + recortar(texto, 400).replace("\n", "\n     ")))
                self.esp.log(f"resultado {u.name}: {recortar(texto, 1000)}")
                r = {"type": "tool_result", "tool_use_id": u.id, "content": texto}
                if es_error:
                    r["is_error"] = True
                resultados.append(r)
            self.mensajes.append({"role": "user", "content": resultados})

            if self.autonomo and self.ctx.fin_ciclo:
                return ultimo_texto
