"""Pruebas sin red: un cliente falso imita las respuestas de la API."""

from __future__ import annotations

import json
from types import SimpleNamespace as NS

import pytest

from automaton import acciones
from automaton.agente import Agente, limpiar_tras_respaldo
from automaton.billetera import nivel
from automaton.ciclo import comando_remoto, despertar, puede_trabajar
from automaton.espacio import Espacio
from automaton.herramientas import Contexto, ErrorHerramienta, ejecutar, ejecutar_seguro, ruta_segura
from automaton.precios import costo_respuesta


@pytest.fixture(autouse=True)
def home_temporal(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOMATON_HOME", str(tmp_path / "datos"))
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    yield


def nuevo(nombre="principal", fondos=5.0, **cfg) -> Espacio:
    esp = Espacio(nombre)
    esp.crear("Ayudarme a organizar mis finanzas personales.", cfg)
    if fondos:
        esp.billetera().registrar("fondeo", fondos, nota="test")
    return esp


# --- respuestas falsas ---------------------------------------------------------
def uso(entrada=1000, salida=500, **extra):
    return NS(input_tokens=entrada, output_tokens=salida, cache_creation_input_tokens=0,
              cache_read_input_tokens=0, iterations=None, server_tool_use=None, **extra)


def texto(t):
    return NS(type="text", text=t)


def herramienta(nombre, entrada, id_="tu_1"):
    return NS(type="tool_use", id=id_, name=nombre, input=entrada)


def respuesta(contenido, stop="end_turn", u=None, model="claude-opus-5-5"):
    return NS(content=contenido, stop_reason=stop, usage=u or uso(), model=model, stop_details=None)


class ClienteFalso:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []
        self.beta = NS(messages=NS(create=self._create))

    def _create(self, **kw):
        self.llamadas.append(json.loads(json.dumps(kw, default=lambda o: o.__dict__)))
        if not self.respuestas:
            return respuesta([texto("(sin más respuestas)")])
        return self.respuestas.pop(0)


# --- precios -------------------------------------------------------------------
def test_costo_opus_55():
    r = respuesta([], u=uso(entrada=1_000_000, salida=100_000))
    assert costo_respuesta(r, "claude-opus-5-5") == pytest.approx(4.0 + 2.0)


def test_costo_con_respaldo_suma_iteraciones():
    its = [
        NS(type="message", model=None, input_tokens=1000, output_tokens=0,
           cache_creation_input_tokens=0, cache_read_input_tokens=0),
        NS(type="fallback_message", model="claude-opus-4-8", input_tokens=1000, output_tokens=1000,
           cache_creation_input_tokens=0, cache_read_input_tokens=0),
    ]
    r = respuesta([], u=NS(input_tokens=1000, output_tokens=1000, cache_creation_input_tokens=0,
                           cache_read_input_tokens=0, iterations=its,
                           server_tool_use=NS(web_search_requests=2, web_fetch_requests=0)))
    esperado = 1000 * 4 / 1e6 + (1000 * 5 + 1000 * 25) / 1e6 + 2 * 0.01
    assert costo_respuesta(r, "claude-opus-5-5") == pytest.approx(esperado)


# --- billetera -----------------------------------------------------------------
def test_billetera_y_niveles():
    esp = nuevo(fondos=3.0)
    b = esp.billetera()
    b.registrar("gasto", 1.5, nota="x")
    assert b.saldo() == pytest.approx(1.5)
    assert b.consumido_hoy() == pytest.approx(1.5)
    cfg = esp.config()
    assert nivel(1.5, cfg) == "ahorro"
    assert nivel(0.1, cfg) == "critico"
    assert nivel(0, cfg) == "sin_fondos"
    assert nivel(10, cfg) == "normal"


# --- seguridad de rutas --------------------------------------------------------
def test_ruta_segura_bloquea_salidas(tmp_path):
    base = tmp_path / "ws"
    base.mkdir()
    for mala in ["../x", "/etc/passwd", "a/../../x"]:
        with pytest.raises(ErrorHerramienta):
            ruta_segura(base, mala)
    (tmp_path / "secreto").write_text("no")
    (base / "enlace").symlink_to(tmp_path / "secreto")
    with pytest.raises(ErrorHerramienta):
        ruta_segura(base, "enlace")
    assert ruta_segura(base, "sub/ok.txt") == (base / "sub/ok.txt").resolve()


def test_herramientas_de_archivos_y_memoria():
    esp = nuevo()
    ctx = Contexto(esp, esp.config())
    ejecutar("archivo_escribir", {"ruta": "notas/a.txt", "contenido": "hola"}, ctx)
    assert ejecutar("archivo_leer", {"ruta": "notas/a.txt"}, ctx) == "hola"
    assert "a.txt" in ejecutar("archivo_listar", {"ruta": "notas"}, ctx)
    ejecutar("memoria_escribir", {"nombre": "diario", "contenido": "día 1", "modo": "reemplazar"}, ctx)
    ejecutar("memoria_escribir", {"nombre": "diario.md", "contenido": "día 2", "modo": "agregar"}, ctx)
    assert ejecutar("memoria_leer", {"nombre": "diario"}, ctx) == "día 1\ndía 2"
    texto_, err = ejecutar_seguro("memoria_escribir", {"nombre": "../../config", "contenido": "x", "modo": "reemplazar"}, ctx)
    assert err


# --- aprobaciones ----------------------------------------------------------------
def test_comando_queda_pendiente_y_se_ejecuta_al_aprobar():
    esp = nuevo()
    ctx = Contexto(esp, esp.config(), confirmar=None)
    salida = ejecutar("ejecutar_comando", {"comando": "echo hola > saludo.txt", "motivo": "prueba"}, ctx)
    assert "pendiente" in salida.lower()
    assert not (esp.workspace / "saludo.txt").exists()
    [p] = acciones.todas_pendientes()
    acciones.resolver(p["id"], True)
    assert (esp.workspace / "saludo.txt").read_text().strip() == "hola"
    assert any("APROBADA" in m["texto"] for m in esp.bandeja())
    assert acciones.todas_pendientes() == []


def test_comando_en_chat_pregunta_y_respeta_el_no():
    esp = nuevo()
    ctx = Contexto(esp, esp.config(), confirmar=lambda _t: False)
    salida = ejecutar("ejecutar_comando", {"comando": "touch x", "motivo": ""}, ctx)
    assert "rechazó" in salida
    assert not (esp.workspace / "x").exists()


def test_comandos_no_ven_secretos(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secreto")
    monkeypatch.setenv("MI_TOKEN", "otro-secreto")
    esp = nuevo(comandos="libre")
    ctx = Contexto(esp, esp.config())
    salida = ejecutar("ejecutar_comando", {"comando": "env", "motivo": ""}, ctx)
    assert "sk-secreto" not in salida and "otro-secreto" not in salida


def test_habilidad_requiere_aprobacion_y_detecta_manipulacion():
    esp = nuevo()
    ctx = Contexto(esp, esp.config())
    codigo = "import sys\nprint(sys.stdin.read().upper())\n"
    ejecutar("crear_habilidad", {"nombre": "gritar", "descripcion": "mayúsculas", "codigo": codigo}, ctx)
    _, err = ejecutar_seguro("usar_habilidad", {"nombre": "gritar", "entrada": "hola"}, ctx)
    assert err  # todavía no aprobada
    [p] = acciones.todas_pendientes()
    acciones.resolver(p["id"], True)
    salida, err = ejecutar_seguro("usar_habilidad", {"nombre": "gritar", "entrada": "hola"}, ctx)
    assert not err and "HOLA" in salida
    # Si alguien cambia el archivo por fuera, deja de estar aprobada.
    (esp.habilidades / "gritar.py").write_text("print('hackeado')\n")
    _, err = ejecutar_seguro("usar_habilidad", {"nombre": "gritar", "entrada": "hola"}, ctx)
    assert err


def test_pago_siempre_pide_aprobacion_y_descuenta():
    esp = nuevo(fondos=5)
    ctx = Contexto(esp, esp.config())
    ejecutar("solicitar_pago", {"monto_usd": 2, "destinatario": "Servicio X", "concepto": "API"}, ctx)
    assert esp.billetera().saldo() == pytest.approx(5)
    [p] = acciones.todas_pendientes()
    acciones.resolver(p["id"], True)
    assert esp.billetera().saldo() == pytest.approx(3)
    _, err = ejecutar_seguro("solicitar_pago", {"monto_usd": 100, "destinatario": "x", "concepto": "y"}, ctx)
    assert err


def test_subagente_limites_y_transferencia():
    padre = nuevo(fondos=10)
    ctx = Contexto(padre, padre.config())
    _, err = ejecutar_seguro("proponer_subagente", {"nombre": "hijo", "mision": "m", "presupuesto_usd": 6}, ctx)
    assert err  # más de la mitad del saldo
    ejecutar("proponer_subagente", {"nombre": "hijo", "mision": "investigar precios", "presupuesto_usd": 3}, ctx)
    [p] = acciones.todas_pendientes()
    acciones.resolver(p["id"], True)
    hijo = Espacio("hijo")
    assert hijo.existe()
    assert hijo.config()["es_subagente"] and hijo.config()["padre"] == "principal"
    assert padre.billetera().saldo() == pytest.approx(7)
    assert hijo.billetera().saldo() == pytest.approx(3)
    # Un subagente no puede tener descendencia.
    ctx_hijo = Contexto(hijo, hijo.config())
    _, err = ejecutar_seguro("proponer_subagente", {"nombre": "nieto", "mision": "m", "presupuesto_usd": 1}, ctx_hijo)
    assert err


# --- bucle del agente ------------------------------------------------------------
def test_bucle_ejecuta_herramientas_y_cobra():
    esp = nuevo(fondos=5)
    cliente = ClienteFalso([
        respuesta([texto("Voy a anotar."), herramienta("memoria_escribir",
                  {"nombre": "diario", "contenido": "empecé", "modo": "reemplazar"})], stop="tool_use"),
        respuesta([texto("Listo.")]),
    ])
    ag = Agente(esp, cliente, autonomo=False, salida=lambda *_: None)
    final = ag.turno("hola")
    assert final == "Listo."
    assert (esp.memoria / "diario.md").read_text() == "empecé"
    assert len(cliente.llamadas) == 2
    # Cada llamada se descontó: 2 x (1000 entrada + 500 salida) a precio de Opus 5.5
    assert esp.billetera().saldo() == pytest.approx(5 - 2 * (1000 * 4 + 500 * 20) / 1e6)
    pedido = cliente.llamadas[0]
    assert pedido["model"] == "claude-opus-5-5"
    assert pedido["fallbacks"] == "default"
    assert pedido["thinking"]["type"] == "adaptive"
    assert pedido["output_config"]["effort"] == "medium"
    # El resultado de la herramienta vuelve con el id correcto.
    tr = cliente.llamadas[1]["messages"][-1]["content"][0]
    assert tr["type"] == "tool_result" and tr["tool_use_id"] == "tu_1"


def test_tope_por_ciclo_frena_el_bucle():
    esp = nuevo(fondos=5, max_gasto_por_ciclo_usd=0.01)
    caro = uso(entrada=10_000, salida=10_000)  # ~0.24 USD
    cliente = ClienteFalso([
        respuesta([herramienta("consultar_billetera", {}, f"t{i}")], stop="tool_use", u=caro) for i in range(10)
    ])
    ag = Agente(esp, cliente, autonomo=True, salida=lambda *_: None)
    ag.turno("trabaja")
    assert len(cliente.llamadas) == 1


def test_sin_fondos_no_llama_a_la_api():
    esp = nuevo(fondos=0)
    cliente = ClienteFalso([respuesta([texto("no debería")])])
    assert despertar(esp, cliente) == "sin_fondos"
    assert cliente.llamadas == []
    assert "sin fondos" in (esp.dir / "mensajes_para_ti.md").read_text().lower()


def test_pausa_detiene_todo():
    esp = nuevo()
    (esp.dir.parent / "PAUSA_TODO").touch()
    assert puede_trabajar(esp) == (False, "pausado")
    cliente = ClienteFalso([respuesta([texto("x")])])
    despertar(esp, cliente)
    assert cliente.llamadas == []


def test_despertar_y_dormir():
    esp = nuevo()
    esp.dejar_en_bandeja("humano", "revisa mis gastos de noviembre")
    cliente = ClienteFalso([
        respuesta([herramienta("dormir", {"minutos": 120, "motivo": "nada urgente"})], stop="tool_use"),
    ])
    assert despertar(esp, cliente) == "ok"
    assert len(cliente.llamadas) == 1  # dormir cierra el ciclo sin otra llamada
    primer_msg = cliente.llamadas[0]["messages"][0]["content"]
    assert "revisa mis gastos de noviembre" in primer_msg and "PRIMER ciclo" in primer_msg
    est = esp.estado()
    assert est["ciclos"] == 1 and "proximo_despertar" in est
    assert esp.bandeja_sin_leer(marcar=False) == []


def test_limpiar_tras_respaldo():
    contenido = [
        NS(type="thinking", thinking="", signature="s"),
        texto("parcial"),
        NS(type="tool_use", id="x", name="memoria_leer", input={"nombre": ""}),
        NS(type="fallback", to=NS(model="claude-opus-4-8")),
        NS(type="thinking", thinking="", signature="s2"),
        herramienta("consultar_billetera", {}, "y"),
    ]
    limpio = limpiar_tras_respaldo(contenido)
    assert [b.type for b in limpio] == ["text", "fallback", "thinking", "tool_use"]
    assert limpio[-1].id == "y"


def test_control_remoto():
    nuevo()
    assert "principal" in comando_remoto("/estado", "principal")
    comando_remoto("/fondear 2,5", "principal")
    assert Espacio("principal").billetera().saldo() == pytest.approx(7.5)
    assert "mayor que 0" in comando_remoto("/fondear -3", "principal")
    comando_remoto("hola agente", "principal")
    assert Espacio("principal").bandeja()[-1]["texto"] == "hola agente"
