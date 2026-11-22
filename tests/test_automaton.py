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


def test_latido_despierta_solo_a_quien_le_toca():
    from automaton.ciclo import latido
    esp = nuevo()
    cliente = ClienteFalso([
        respuesta([herramienta("dormir", {"minutos": 180, "motivo": "nada urgente"})], stop="tool_use"),
    ])
    latido(None, cliente)
    assert len(cliente.llamadas) == 1
    latido(None, cliente)  # todavía no le toca: no llama al modelo
    assert len(cliente.llamadas) == 1
    esp.dejar_en_bandeja("humano", "¿cómo vas?")  # un mensaje tuyo lo despierta antes
    latido(None, cliente)
    assert len(cliente.llamadas) == 2


# --- oportunidades de ingreso -----------------------------------------------------
def _op(ctx, titulo, ingreso, prob, costo, horas, categoria="freelance"):
    salida = ejecutar("oportunidad_registrar", {
        "titulo": titulo, "descripcion": "d", "categoria": categoria, "ingreso_estimado_usd": ingreso,
        "probabilidad": prob, "costo_estimado_usd": costo, "horas_tuyas": horas, "primer_paso": "hacer algo",
    }, ctx)
    return salida.split("[")[1].split("]")[0]


def test_ranking_por_ganancia_por_hora():
    from automaton import oportunidades as ops
    esp = nuevo()
    ctx = Contexto(esp, esp.config())
    a = _op(ctx, "Mucho dinero, mucho tiempo", 1000, 0.5, 0, 100)   # 500 / 100 h = 5 $/h
    b = _op(ctx, "Poco dinero, poco tiempo", 100, 0.8, 0, 4)        # 80 / 4 h = 20 $/h
    c = _op(ctx, "Cara y dudosa", 300, 0.1, 50, 2)                  # -20 / 2 h = -10 $/h
    orden = [op["id"] for op in ops.activas_ordenadas(esp)]
    assert orden == [b, a, c]
    texto_ = ejecutar("oportunidades_ranking", {}, ctx)
    assert texto_.index(b) < texto_.index(a) < texto_.index(c)
    # Probabilidad fuera de rango -> error para el modelo
    _, err = ejecutar_seguro("oportunidad_registrar", {
        "titulo": "x", "descripcion": "", "categoria": "x", "ingreso_estimado_usd": 1, "probabilidad": 3,
        "costo_estimado_usd": 0, "horas_tuyas": 1, "primer_paso": "",
    }, ctx)
    assert err


def test_el_agente_no_puede_marcar_ganada_ni_poner_en_marcha():
    esp = nuevo()
    ctx = Contexto(esp, esp.config())
    id_ = _op(ctx, "Idea", 100, 0.5, 0, 2)
    base = {"id": id_, "nota": "", "probabilidad": None, "ingreso_estimado_usd": None}
    _, err = ejecutar_seguro("oportunidad_actualizar", {**base, "estado": "ganada"}, ctx)
    assert err
    salida, err = ejecutar_seguro("oportunidad_actualizar", {**base, "estado": "propuesta", "probabilidad": 0.7}, ctx)
    assert not err and "propuesta" in salida


def test_aprobar_oportunidad_ingreso_comision_y_calibracion():
    from automaton import oportunidades as ops
    esp = nuevo(fondos=5)
    ctx = Contexto(esp, esp.config())
    id_ = _op(ctx, "Clases particulares", 200, 0.5, 0, 10, categoria="servicios")
    ops.decidir(f" {id_.upper()} ", True)  # tolera espacios y mayúsculas
    assert ops.cargar(esp)[0]["estado"] == "en_marcha"
    assert "EN MARCHA" in esp.bandeja()[-1]["texto"]
    ops.registrar_ingreso(esp, 150, id_, "3 alumnos")
    op = ops.cargar(esp)[0]
    assert op["estado"] == "ganada" and op["ingreso_real_usd"] == 150
    assert esp.billetera().saldo() == pytest.approx(5 + 15)  # 10 % de comisión
    est = ops.estadisticas(esp)
    assert est["total_real"] == 150 and est["calibracion"] == 0.75
    assert "optimista" in ops.ranking_texto(esp)
    assert est["por_categoria"]["servicios"]["ganadas"] == 1


def test_cli_ingreso_y_aprobar(capsys):
    from automaton.__main__ import main
    from automaton import oportunidades as ops
    esp = nuevo(fondos=1)
    op = ops.registrar(esp, "Vender ropa usada", "", "reventa", 80, 0.6, 0, 5, "fotos")
    main(["aprobar", op["id"]])
    main(["ingreso", "40,5", op["id"], "vendí", "dos", "camperas"])
    op2 = ops.cargar(esp)[0]
    assert op2["estado"] == "ganada" and op2["ingreso_real_usd"] == 40.5
    assert "vendí dos camperas" in op2["notas"][-1]
    main(["ideas"])
    assert "40.50" in capsys.readouterr().out


# --- rutinas diarias -----------------------------------------------------------------
def test_rutina_de_la_manana(monkeypatch):
    from datetime import datetime, timedelta
    import automaton.ciclo as ciclo
    esp = nuevo()
    ayer = datetime(2026, 11, 22, 15, 0).astimezone()
    esp.actualizar_estado(creado=ayer.isoformat(), ciclos=3,
                          proximo_despertar=(ayer + timedelta(days=5)).isoformat())
    reloj = {"t": datetime(2026, 11, 23, 7, 30).astimezone()}
    monkeypatch.setattr(ciclo, "ahora", lambda: reloj["t"])

    assert ciclo.rutina_pendiente(esp) is None          # 7:30, todavía no
    assert not ciclo.toca_despertar(esp)
    reloj["t"] = datetime(2026, 11, 23, 8, 23).astimezone()
    r = ciclo.rutina_pendiente(esp)
    assert r and r["nombre"] == "plan_del_dia" and "oportunidades_ranking" in r["instruccion"]
    assert ciclo.toca_despertar(esp)                     # la rutina adelanta el despertar

    cliente = ClienteFalso([respuesta([herramienta("dormir", {"minutos": 240, "motivo": "listo"})], stop="tool_use")])
    ciclo.despertar(esp, cliente)
    assert "RUTINA DIARIA «plan_del_dia»" in cliente.llamadas[0]["messages"][0]["content"]
    assert ciclo.rutina_pendiente(esp) is None           # ya se hizo hoy
    reloj["t"] = datetime(2026, 11, 24, 8, 30).astimezone()
    assert ciclo.rutina_pendiente(esp) is not None       # al día siguiente vuelve


def test_rutina_no_corre_el_dia_de_creacion_ni_en_subagentes(monkeypatch):
    from datetime import datetime
    import automaton.ciclo as ciclo
    esp = nuevo(fondos=10)
    esp.actualizar_estado(creado=datetime(2026, 11, 23, 10, 0).astimezone().isoformat())
    monkeypatch.setattr(ciclo, "ahora", lambda: datetime(2026, 11, 23, 11, 0).astimezone())
    assert ciclo.rutina_pendiente(esp) is None
    acciones.crear_subagente(esp, "hijo", "m", 2)
    assert Espacio("hijo").config()["rutinas"] == []


def test_control_remoto_oportunidades():
    from automaton import oportunidades as ops
    esp = nuevo()
    op = ops.registrar(esp, "Diseño de logos", "", "freelance", 120, 0.5, 0, 6, "portfolio")
    assert op["id"] in comando_remoto("/ideas", "principal")
    assert "En marcha" in comando_remoto(f"/aprobar {op['id']}", "principal")
    assert "Comisión" in comando_remoto(f"/ingreso 60 {op['id']} primer cliente", "principal")
    assert ops.cargar(esp)[0]["estado"] == "ganada"
