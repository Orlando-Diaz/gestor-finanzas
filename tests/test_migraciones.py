import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

import app.models  # noqa: F401
from app.core.database import Base
from app.core.migraciones import configuracion_alembic, preparar_base_de_datos

TABLAS = {
    "usuarios", "cuentas", "categorias", "transacciones", "presupuestos",
    "transacciones_recurrentes", "notificaciones",
    "metas", "aportes_meta", "deudas", "pagos_deuda",
}


@pytest.fixture()
def motor(tmp_path):
    motor = create_engine(f"sqlite:///{tmp_path / 'migraciones.db'}")
    yield motor
    motor.dispose()


def tablas(motor):
    with motor.connect() as c:
        return set(inspect(c).get_table_names())


def test_las_migraciones_crean_todas_las_tablas(motor):
    preparar_base_de_datos(motor)
    assert tablas(motor) == TABLAS | {"alembic_version"}


def test_las_migraciones_coinciden_con_los_modelos(motor):
    """Si cambias un modelo y olvidas crear la migración, esta prueba falla."""
    preparar_base_de_datos(motor)
    with motor.connect() as c:
        diferencias = compare_metadata(MigrationContext.configure(c, opts={"compare_type": True}), Base.metadata)
    assert diferencias == [], f"Faltan migraciones: {diferencias}"


def test_preparar_es_idempotente(motor):
    preparar_base_de_datos(motor)
    preparar_base_de_datos(motor)
    with motor.connect() as c:
        assert c.execute(text("select version_num from alembic_version")).scalars().all() == ["0002"]


def test_subir_bajar_y_volver_a_subir(motor):
    preparar_base_de_datos(motor)
    with motor.begin() as c:
        command.downgrade(configuracion_alembic(c), "base")
    assert tablas(motor) == {"alembic_version"}
    preparar_base_de_datos(motor)
    assert TABLAS <= tablas(motor)


def test_base_creada_sin_migraciones_da_un_error_claro(motor):
    Base.metadata.create_all(motor)  # lo que hacía la versión anterior de la app
    with pytest.raises(RuntimeError, match="mis_finanzas.db"):
        preparar_base_de_datos(motor)


def test_las_restricciones_de_la_migracion_se_aplican(motor):
    """El esquema migrado debe rechazar datos inválidos igual que el de los modelos."""
    preparar_base_de_datos(motor)
    with motor.begin() as c:
        c.execute(text("PRAGMA foreign_keys=ON"))
        c.execute(text("insert into usuarios (id, nombre, email, password_hash, moneda_por_defecto, activo, creado_en) "
                       "values (1, 'A', 'a@a.co', 'x', 'COP', 1, '2026-01-01')"))
        c.execute(text("insert into cuentas (id, usuario_id, nombre, tipo, saldo_inicial, archivada) "
                       "values (1, 1, 'Efectivo', 'EFECTIVO', 0, 0)"))
    with pytest.raises(Exception, match="(?i)constraint|check"):
        with motor.begin() as c:
            c.execute(text("PRAGMA foreign_keys=ON"))
            c.execute(text(
                "insert into transacciones (usuario_id, cuenta_id, tipo, monto, fecha, creado_en, actualizado_en) "
                "values (1, 1, 'GASTO', 0, '2026-10-01', '2026-10-01', '2026-10-01')"))  # monto 0
