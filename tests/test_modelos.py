from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import (
    Categoria,
    Cuenta,
    TipoCategoria,
    TipoCuenta,
    TipoTransaccion,
    Transaccion,
    Usuario,
)
from app.schemas.transaccion import TransaccionCrear


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def datos(db):
    u = Usuario(nombre="Orlando", email="o@test.co", password_hash="x")
    db.add(u)
    db.flush()
    efectivo = Cuenta(usuario_id=u.id, nombre="Efectivo", tipo=TipoCuenta.EFECTIVO, saldo_inicial=Decimal("50000"))
    nequi = Cuenta(usuario_id=u.id, nombre="Nequi", tipo=TipoCuenta.BILLETERA_DIGITAL, saldo_inicial=Decimal("200000"))
    banco = Cuenta(usuario_id=u.id, nombre="Bancolombia", tipo=TipoCuenta.BANCARIA, saldo_inicial=Decimal("1500000"))
    comida = Categoria(usuario_id=None, nombre="Comida", tipo=TipoCategoria.GASTO)
    db.add_all([efectivo, nequi, banco, comida])
    db.commit()
    return u, efectivo, nequi, banco, comida


def saldo(db, cuenta):
    """Saldo = inicial + ingresos - gastos - transferencias salientes + entrantes."""
    def suma(*condiciones):
        return db.scalar(select(func.coalesce(func.sum(Transaccion.monto), 0)).where(*condiciones)) or Decimal(0)

    ing = suma(Transaccion.cuenta_id == cuenta.id, Transaccion.tipo == TipoTransaccion.INGRESO)
    gas = suma(Transaccion.cuenta_id == cuenta.id, Transaccion.tipo == TipoTransaccion.GASTO)
    sal = suma(Transaccion.cuenta_id == cuenta.id, Transaccion.tipo == TipoTransaccion.TRANSFERENCIA)
    ent = suma(Transaccion.cuenta_destino_id == cuenta.id, Transaccion.tipo == TipoTransaccion.TRANSFERENCIA)
    return cuenta.saldo_inicial + Decimal(ing) - Decimal(gas) - Decimal(sal) + Decimal(ent)


def test_ejemplo_del_almuerzo_y_cajero(db, datos):
    u, efectivo, nequi, banco, comida = datos
    db.add_all([
        Transaccion(usuario_id=u.id, cuenta_id=efectivo.id, categoria_id=comida.id,
                    tipo=TipoTransaccion.GASTO, monto=Decimal("18000"), fecha=date(2026, 9, 29), nota="Almuerzo"),
        Transaccion(usuario_id=u.id, cuenta_id=banco.id, cuenta_destino_id=efectivo.id,
                    tipo=TipoTransaccion.TRANSFERENCIA, monto=Decimal("100000"), fecha=date(2026, 9, 29), nota="Cajero"),
    ])
    db.commit()
    assert saldo(db, efectivo) == Decimal("50000") - Decimal("18000") + Decimal("100000")  # 132.000
    assert saldo(db, banco) == Decimal("1400000")
    assert saldo(db, nequi) == Decimal("200000")


def test_bd_rechaza_monto_no_positivo(db, datos):
    u, efectivo, _, _, comida = datos
    db.add(Transaccion(usuario_id=u.id, cuenta_id=efectivo.id, categoria_id=comida.id,
                       tipo=TipoTransaccion.GASTO, monto=Decimal("0"), fecha=date(2026, 9, 29)))
    with pytest.raises(IntegrityError):
        db.commit()


def test_bd_rechaza_transferencia_a_la_misma_cuenta(db, datos):
    u, efectivo, *_ = datos
    db.add(Transaccion(usuario_id=u.id, cuenta_id=efectivo.id, cuenta_destino_id=efectivo.id,
                       tipo=TipoTransaccion.TRANSFERENCIA, monto=Decimal("1000"), fecha=date(2026, 9, 29)))
    with pytest.raises(IntegrityError):
        db.commit()


def test_bd_rechaza_gasto_con_cuenta_destino(db, datos):
    u, efectivo, nequi, _, comida = datos
    db.add(Transaccion(usuario_id=u.id, cuenta_id=efectivo.id, cuenta_destino_id=nequi.id,
                       categoria_id=comida.id, tipo=TipoTransaccion.GASTO, monto=Decimal("1000"),
                       fecha=date(2026, 9, 29)))
    with pytest.raises(IntegrityError):
        db.commit()


def test_cuenta_duplicada_por_usuario(db, datos):
    u, *_ = datos
    db.add(Cuenta(usuario_id=u.id, nombre="Nequi", tipo=TipoCuenta.BILLETERA_DIGITAL))
    with pytest.raises(IntegrityError):
        db.commit()


def test_esquema_valida_reglas_de_transferencia():
    base = dict(monto="1000", fecha=date(2026, 9, 29), cuenta_id=1)
    TransaccionCrear(tipo="GASTO", categoria_id=3, **base)
    TransaccionCrear(tipo="TRANSFERENCIA", cuenta_destino_id=2, **base)
    with pytest.raises(ValidationError):
        TransaccionCrear(tipo="TRANSFERENCIA", **base)  # sin destino
    with pytest.raises(ValidationError):
        TransaccionCrear(tipo="TRANSFERENCIA", cuenta_destino_id=1, **base)  # mismo origen y destino
    with pytest.raises(ValidationError):
        TransaccionCrear(tipo="GASTO", **base)  # sin categoría
    with pytest.raises(ValidationError):
        TransaccionCrear(tipo="GASTO", categoria_id=3, monto="-5", fecha=date(2026, 9, 29), cuenta_id=1)
