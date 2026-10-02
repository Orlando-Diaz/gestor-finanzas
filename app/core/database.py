from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

_es_sqlite = settings.database_url.startswith("sqlite")

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _es_sqlite else {},
    # Bases en la nube que se "duermen" cierran conexiones: se comprueba antes de usarla
    pool_pre_ping=not _es_sqlite,
)

if _es_sqlite:
    # SQLite no aplica llaves foráneas por defecto
    @event.listens_for(engine, "connect")
    def _activar_fk(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
