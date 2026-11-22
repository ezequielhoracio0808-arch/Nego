"""Control desde el celular por Telegram (opcional).

Configura dos variables de entorno:
    TELEGRAM_BOT_TOKEN   token de tu bot (créalo con @BotFather)
    TELEGRAM_CHAT_ID     tu chat id (solo se aceptan órdenes de este chat)

Comandos que entiende (solo mientras corre `python -m automaton vivir`):
    /estado                    saldo y nivel de cada agente
    /pendientes                acciones que esperan tu aprobación
    /aprobar <id>              aprueba y ejecuta una acción pendiente
    /rechazar <id> [razón]     la rechaza
    /fondear <usd> [agente]    agrega presupuesto
    /pausa  /reanudar          interruptor general
    cualquier otro texto       se deja en la bandeja del agente principal y lo despierta
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from .espacio import home

API = "https://api.telegram.org/bot{token}/{metodo}"


def configurado() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


def _llamar(metodo: str, params: dict, timeout: float = 20) -> dict:
    url = API.format(token=os.environ["TELEGRAM_BOT_TOKEN"], metodo=metodo)
    datos = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(url, data=datos, timeout=timeout) as r:
        return json.loads(r.read().decode())


def enviar(texto: str) -> bool:
    if not configurado():
        return False
    try:
        for i in range(0, len(texto), 4000):  # límite de Telegram ~4096
            _llamar("sendMessage", {"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": texto[i : i + 4000]})
        return True
    except Exception as e:  # nunca romper el agente por un aviso fallido
        print(f"[telegram] no se pudo enviar: {e}")
        return False


def recibir() -> list[str]:
    """Devuelve los textos nuevos enviados desde TU chat (ignora a cualquier otro)."""
    if not configurado():
        return []
    ruta_offset = home() / "telegram_offset.txt"
    offset = int(ruta_offset.read_text()) if ruta_offset.exists() else 0
    try:
        r = _llamar("getUpdates", {"offset": offset, "timeout": 0}, timeout=15)
    except Exception as e:
        print(f"[telegram] no se pudo leer: {e}")
        return []
    textos = []
    mi_chat = str(os.environ["TELEGRAM_CHAT_ID"])
    for upd in r.get("result", []):
        offset = max(offset, upd["update_id"] + 1)
        msg = upd.get("message") or {}
        if str(msg.get("chat", {}).get("id")) == mi_chat and msg.get("text"):
            textos.append(msg["text"])
    ruta_offset.parent.mkdir(parents=True, exist_ok=True)
    ruta_offset.write_text(str(offset))
    return textos
