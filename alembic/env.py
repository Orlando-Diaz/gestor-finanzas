from alembic import context
from sqlalchemy import create_engine

import app.models  # noqa: F401  (registra todas las tablas en Base.metadata)
from app.core.config import settings
from app.core.database import Base

target_metadata = Base.metadata
config = context.config


def _configurar(**kwargs):
    context.configure(
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=True,  # SQLite no soporta ALTER TABLE completo: Alembic recrea la tabla
        **kwargs,
    )


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse (alembic upgrade head --sql)."""
    _configurar(url=settings.database_url, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Si quien llama (la app o las pruebas) ya trae una conexión, se usa esa.
    conexion = config.attributes.get("connection")
    if conexion is not None:
        _configurar(connection=conexion)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = create_engine(settings.database_url)
    with engine.connect() as conexion:
        _configurar(connection=conexion)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
