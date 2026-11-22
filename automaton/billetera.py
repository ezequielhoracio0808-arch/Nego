"""La billetera del agente: un libro contable en USD, solo de anexado.

El agente NO tiene acceso a dinero real. La billetera es un presupuesto que tú
le asignas ("fondear") y del que se descuenta cada llamada al modelo. Cuando se
acaba, el agente se detiene. Solo tú puedes agregar fondos o registrar ingresos;
el agente no tiene ninguna herramienta para subir su propio saldo.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

# Tipos que suman (positivos) y que restan (negativos) al saldo.
ENTRADAS = {"fondeo", "ingreso", "transferencia_entrada", "ajuste"}
SALIDAS = {"gasto", "pago", "transferencia_salida"}
# Lo que cuenta para los topes de gasto (diario y por ciclo).
CONSUMO = {"gasto", "pago"}


def ahora() -> datetime:
    return datetime.now().astimezone()


class Billetera:
    def __init__(self, ruta: Path):
        self.ruta = Path(ruta)

    def movimientos(self) -> list[dict]:
        if not self.ruta.exists():
            return []
        salida = []
        for linea in self.ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea:
                salida.append(json.loads(linea))
        return salida

    def registrar(self, tipo: str, monto: float, nota: str = "", **detalle) -> dict:
        if tipo not in ENTRADAS | SALIDAS:
            raise ValueError(f"Tipo de movimiento desconocido: {tipo}")
        monto = abs(float(monto))
        if tipo in SALIDAS:
            monto = -monto
        mov = {
            "ts": ahora().isoformat(timespec="seconds"),
            "tipo": tipo,
            "monto": round(monto, 6),
            "nota": nota,
        }
        if detalle:
            mov["detalle"] = detalle
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with self.ruta.open("a", encoding="utf-8") as f:
            f.write(json.dumps(mov, ensure_ascii=False) + "\n")
        return mov

    def saldo(self) -> float:
        return round(sum(m["monto"] for m in self.movimientos()), 6)

    def consumido_desde(self, desde: datetime) -> float:
        total = 0.0
        for m in self.movimientos():
            if m["tipo"] in CONSUMO and datetime.fromisoformat(m["ts"]) >= desde:
                total += -m["monto"]
        return round(total, 6)

    def consumido_hoy(self) -> float:
        inicio = ahora().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.consumido_desde(inicio)


def nivel(saldo: float, cfg: dict) -> str:
    """Nivel de "supervivencia" según el saldo, como en Automaton.

    - normal: trabaja con el esfuerzo configurado.
    - ahorro: baja el esfuerzo para gastar menos.
    - critico: en modo autónomo no llama al modelo; solo te avisa.
    - sin_fondos: no hace nada hasta que lo fondees.
    """
    if saldo <= 0:
        return "sin_fondos"
    if saldo < cfg["umbral_critico_usd"]:
        return "critico"
    if saldo < cfg["umbral_ahorro_usd"]:
        return "ahorro"
    return "normal"
