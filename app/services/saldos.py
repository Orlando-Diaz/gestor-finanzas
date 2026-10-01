from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import TipoTransaccion, Transaccion

CENTAVOS = Decimal("0.01")


def deltas_por_cuenta(db: Session, usuario_id: int) -> dict[int, Decimal]:
    """Movimiento neto de cada cuenta (sin el saldo inicial).

    ingreso suma, gasto resta, transferencia resta en el origen y suma en el destino.
    """
    T = Transaccion
    origen = (
        select(
            T.cuenta_id.label("cuenta_id"),
            func.sum(case((T.tipo == TipoTransaccion.INGRESO, T.monto), else_=-T.monto)).label("delta"),
        )
        .where(T.usuario_id == usuario_id)
        .group_by(T.cuenta_id)
    )
    destino = (
        select(T.cuenta_destino_id.label("cuenta_id"), func.sum(T.monto).label("delta"))
        .where(T.usuario_id == usuario_id, T.tipo == TipoTransaccion.TRANSFERENCIA)
        .group_by(T.cuenta_destino_id)
    )
    resultado: dict[int, Decimal] = {}
    for consulta in (origen, destino):
        for cuenta_id, delta in db.execute(consulta):
            resultado[cuenta_id] = resultado.get(cuenta_id, Decimal(0)) + Decimal(str(delta))
    return resultado


def saldo_actual(saldo_inicial: Decimal, delta: Decimal | None) -> Decimal:
    return (Decimal(saldo_inicial) + (delta or Decimal(0))).quantize(CENTAVOS)
