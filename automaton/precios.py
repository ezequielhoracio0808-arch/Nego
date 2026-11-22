"""Cálculo del costo en USD de cada llamada al modelo.

Los precios son USD por millón de tokens. Son una estimación para que el agente
lleve sus cuentas; la factura real la emite Anthropic. Revisa
https://platform.claude.com/docs/en/about-claude/pricing si cambian.
"""

from __future__ import annotations

# modelo: (entrada, salida, escritura de caché 5 min, lectura de caché)
PRECIOS: dict[str, tuple[float, float, float, float]] = {
    "claude-opus-5-5": (4.00, 20.00, 5.00, 0.20),
    "claude-opus-5": (5.00, 25.00, 6.25, 0.50),
    "claude-opus-4-8": (5.00, 25.00, 6.25, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00, 2.50, 0.10),
    "claude-sonnet-5": (2.00, 10.00, 2.50, 0.20),
    "claude-haiku-5-5": (0.10, 0.50, 0.125, 0.01),
}

# Si aparece un modelo que no conocemos (p. ej. un modelo de respaldo nuevo),
# cobramos de más a propósito: mejor sobreestimar el gasto que quedarse corto.
PRECIO_DESCONOCIDO = (10.00, 50.00, 12.50, 1.00)

# Búsqueda web del servidor: 10 USD cada 1000 búsquedas.
COSTO_BUSQUEDA_WEB = 0.01


def precio(modelo: str | None) -> tuple[float, float, float, float]:
    if not modelo:
        return PRECIO_DESCONOCIDO
    if modelo in PRECIOS:
        return PRECIOS[modelo]
    # Coincidencia por prefijo más largo (por si llega un alias con sufijo).
    candidatos = [k for k in PRECIOS if modelo.startswith(k)]
    if candidatos:
        return PRECIOS[max(candidatos, key=len)]
    return PRECIO_DESCONOCIDO


def costo_tokens(
    modelo: str | None,
    entrada: int,
    salida: int,
    cache_escritura: int = 0,
    cache_lectura: int = 0,
) -> float:
    p_in, p_out, p_cw, p_cr = precio(modelo)
    return (
        entrada * p_in
        + salida * p_out
        + cache_escritura * p_cw
        + cache_lectura * p_cr
    ) / 1_000_000


def _n(obj, campo: str) -> int:
    return int(getattr(obj, campo, 0) or 0)


def costo_respuesta(resp, modelo_pedido: str) -> float:
    """Costo total de una respuesta, incluidos los intentos de respaldo.

    `usage.iterations` es la fuente de verdad por intento cuando existe (por
    ejemplo, si el modelo pedido declinó y respondió un modelo de respaldo);
    el `usage` de nivel superior solo cubre el intento que produjo el mensaje.
    """
    uso = resp.usage
    total = 0.0
    iteraciones = getattr(uso, "iterations", None) or []
    if iteraciones:
        for it in iteraciones:
            modelo = getattr(it, "model", None) or modelo_pedido
            total += costo_tokens(
                modelo,
                _n(it, "input_tokens"),
                _n(it, "output_tokens"),
                _n(it, "cache_creation_input_tokens"),
                _n(it, "cache_read_input_tokens"),
            )
    else:
        total += costo_tokens(
            getattr(resp, "model", None) or modelo_pedido,
            _n(uso, "input_tokens"),
            _n(uso, "output_tokens"),
            _n(uso, "cache_creation_input_tokens"),
            _n(uso, "cache_read_input_tokens"),
        )
    herramientas_servidor = getattr(uso, "server_tool_use", None)
    if herramientas_servidor is not None:
        total += _n(herramientas_servidor, "web_search_requests") * COSTO_BUSQUEDA_WEB
    return total
