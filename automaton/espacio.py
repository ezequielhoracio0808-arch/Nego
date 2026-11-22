"""Dónde vive cada agente en disco: configuración, memoria, billetera, bandeja...

Estructura (por defecto bajo ./datos, o la carpeta de AUTOMATON_HOME):

    datos/
      PAUSA_TODO              <- si existe, ningún agente se ejecuta (interruptor general)
      principal/
        config.json
        identidad.md          <- su "alma": misión y estrategia (el agente puede reescribirla)
        billetera.jsonl       <- libro contable
        bandeja.jsonl         <- mensajes para el agente (tuyos o resultados de aprobaciones)
        pendientes.json       <- acciones que esperan tu aprobación
        mensajes_para_ti.md   <- avisos del agente para ti
        registro.log          <- todo lo que hizo
        estado.json
        memoria/              <- notas persistentes entre ciclos
        workspace/            <- su carpeta de trabajo
        habilidades/          <- herramientas que él mismo programó
        PAUSA                 <- si existe, este agente no se ejecuta
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .billetera import Billetera, ahora

NOMBRE_VALIDO = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")

CONFIG_POR_DEFECTO: dict = {
    "modelo": "claude-opus-5-5",
    # Esfuerzo de razonamiento según el nivel de saldo.
    "esfuerzo": {"normal": "medium", "ahorro": "low", "critico": "low"},
    "max_tokens": 16000,
    # Cada cuántos minutos despierta en modo `vivir` (si no pidió otra cosa).
    "latido_minutos": 60,
    # Límites duros por ciclo y por día.
    "max_llamadas_por_ciclo": 25,
    "max_gasto_por_ciclo_usd": 0.50,
    "max_gasto_diario_usd": 2.00,
    # Umbrales de supervivencia.
    "umbral_ahorro_usd": 2.00,
    "umbral_critico_usd": 0.25,
    # Comandos de terminal: "no" | "aprobar" | "libre".
    # "libre" solo si lo ejecutas dentro de un contenedor o VM desechable.
    "comandos": "aprobar",
    "timeout_comando_seg": 120,
    # Las habilidades nuevas (o modificadas) necesitan tu visto bueno.
    "habilidades_requieren_aprobacion": True,
    # Búsqueda y lectura web (herramientas del servidor de Anthropic).
    "web": True,
    "max_busquedas_por_llamada": 5,
    # Subagentes ("descendencia").
    "max_subagentes": 3,
    "es_subagente": False,
    "padre": None,
}

PLANTILLA_IDENTIDAD = """# Identidad de {nombre}

## Misión
{mision}

## Estrategia actual
(Todavía no definida. Escríbela con `actualizar_identidad` después de tu primer ciclo.)

## Lo que he aprendido
(Vacío por ahora.)
"""


def home() -> Path:
    return Path(os.environ.get("AUTOMATON_HOME", "datos")).resolve()


def listar_agentes() -> list[str]:
    base = home()
    if not base.exists():
        return []
    return sorted(p.name for p in base.iterdir() if (p / "config.json").exists())


def pausa_general() -> bool:
    return (home() / "PAUSA_TODO").exists()


def _leer_json(ruta: Path, defecto):
    if not ruta.exists():
        return defecto
    return json.loads(ruta.read_text(encoding="utf-8"))


def _escribir_json(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(ruta.suffix + ".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(ruta)


class Espacio:
    def __init__(self, nombre: str):
        if not NOMBRE_VALIDO.match(nombre):
            raise ValueError(
                f"Nombre de agente inválido: {nombre!r} "
                "(minúsculas, números, - o _, de 2 a 32 caracteres)"
            )
        self.nombre = nombre
        self.dir = home() / nombre

    # --- rutas -----------------------------------------------------------
    @property
    def memoria(self) -> Path:
        return self.dir / "memoria"

    @property
    def workspace(self) -> Path:
        return self.dir / "workspace"

    @property
    def habilidades(self) -> Path:
        return self.dir / "habilidades"

    def existe(self) -> bool:
        return (self.dir / "config.json").exists()

    def crear(self, mision: str, config_extra: dict | None = None) -> None:
        if self.existe():
            raise FileExistsError(f"El agente '{self.nombre}' ya existe en {self.dir}")
        for d in (self.dir, self.memoria, self.workspace, self.habilidades):
            d.mkdir(parents=True, exist_ok=True)
        cfg = dict(CONFIG_POR_DEFECTO)
        cfg.update(config_extra or {})
        _escribir_json(self.dir / "config.json", cfg)
        self.guardar_identidad(
            PLANTILLA_IDENTIDAD.format(nombre=self.nombre, mision=mision.strip())
        )
        _escribir_json(self.dir / "estado.json", {"creado": ahora().isoformat(timespec="seconds")})

    # --- configuración y estado -------------------------------------------
    def config(self) -> dict:
        cfg = dict(CONFIG_POR_DEFECTO)
        cfg.update(_leer_json(self.dir / "config.json", {}))
        esfuerzo = dict(CONFIG_POR_DEFECTO["esfuerzo"])
        esfuerzo.update(cfg.get("esfuerzo") or {})
        cfg["esfuerzo"] = esfuerzo
        return cfg

    def guardar_config(self, cfg: dict) -> None:
        _escribir_json(self.dir / "config.json", cfg)

    def estado(self) -> dict:
        return _leer_json(self.dir / "estado.json", {})

    def actualizar_estado(self, **cambios) -> None:
        est = self.estado()
        est.update(cambios)
        _escribir_json(self.dir / "estado.json", est)

    def billetera(self) -> Billetera:
        return Billetera(self.dir / "billetera.jsonl")

    def pausado(self) -> bool:
        return (self.dir / "PAUSA").exists() or pausa_general()

    # --- identidad --------------------------------------------------------
    def identidad(self) -> str:
        ruta = self.dir / "identidad.md"
        return ruta.read_text(encoding="utf-8") if ruta.exists() else ""

    def guardar_identidad(self, texto: str) -> None:
        (self.dir / "identidad.md").write_text(texto, encoding="utf-8")

    # --- bandeja de entrada del agente -------------------------------------
    def dejar_en_bandeja(self, de: str, texto: str) -> None:
        msg = {"ts": ahora().isoformat(timespec="seconds"), "de": de, "texto": texto, "leido": False}
        with (self.dir / "bandeja.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    def bandeja(self) -> list[dict]:
        ruta = self.dir / "bandeja.jsonl"
        if not ruta.exists():
            return []
        return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]

    def bandeja_sin_leer(self, marcar: bool = True) -> list[dict]:
        todos = self.bandeja()
        nuevos = [m for m in todos if not m.get("leido")]
        if marcar and nuevos:
            for m in todos:
                m["leido"] = True
            (self.dir / "bandeja.jsonl").write_text(
                "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in todos),
                encoding="utf-8",
            )
        return nuevos

    # --- aprobaciones pendientes -----------------------------------------
    def pendientes(self) -> list[dict]:
        return _leer_json(self.dir / "pendientes.json", [])

    def guardar_pendientes(self, lista: list[dict]) -> None:
        _escribir_json(self.dir / "pendientes.json", lista)

    # --- registro ---------------------------------------------------------
    def log(self, texto: str) -> None:
        marca = ahora().strftime("%Y-%m-%d %H:%M:%S")
        with (self.dir / "registro.log").open("a", encoding="utf-8") as f:
            for linea in str(texto).splitlines() or [""]:
                f.write(f"[{marca}] {linea}\n")

    def anotar_mensaje_para_humano(self, texto: str) -> None:
        marca = ahora().strftime("%Y-%m-%d %H:%M")
        with (self.dir / "mensajes_para_ti.md").open("a", encoding="utf-8") as f:
            f.write(f"\n## {marca} — {self.nombre}\n\n{texto.strip()}\n")
