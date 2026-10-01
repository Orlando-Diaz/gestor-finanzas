from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import Connection, Engine

RAIZ = Path(__file__).resolve().parents[2]


def configuracion_alembic(conexion: Connection | None = None) -> Config:
    """Configuración de Alembic sin depender del directorio desde el que se arranque la app."""
    cfg = Config()
    cfg.set_main_option("script_location", str(RAIZ / "alembic"))
    if conexion is not None:
        cfg.attributes["connection"] = conexion  # alembic/env.py usa esta conexión si existe
    return cfg


def preparar_base_de_datos(engine: Engine) -> None:
    """Deja la base de datos en la versión más reciente del esquema (alembic upgrade head)."""
    with engine.connect() as conexion:
        tablas = set(inspect(conexion).get_table_names())
    if "usuarios" in tablas and "alembic_version" not in tablas:
        raise RuntimeError(
            "La base de datos es anterior a las migraciones (se creó sin Alembic). "
            "Si es de desarrollo, borra el archivo mis_finanzas.db y vuelve a arrancar; "
            "si tiene datos que quieres conservar, ejecuta 'alembic stamp 0001' solo si su esquema coincide."
        )
    with engine.begin() as conexion:
        command.upgrade(configuracion_alembic(conexion), "head")
