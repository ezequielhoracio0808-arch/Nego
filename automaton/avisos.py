"""Cómo el agente te avisa: archivo mensajes_para_ti.md, consola y Telegram."""

from __future__ import annotations

from . import telegram
from .espacio import Espacio


def avisar_humano(esp: Espacio, texto: str) -> None:
    esp.anotar_mensaje_para_humano(texto)
    esp.log(f"AVISO AL HUMANO: {texto}")
    print(f"\n📣 [{esp.nombre}] {texto}\n")
    telegram.enviar(f"[{esp.nombre}] {texto}")
