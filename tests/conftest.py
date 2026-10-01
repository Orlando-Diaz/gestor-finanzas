import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.database import Base, get_db
from app.main import app as fastapi_app
from app.services.categorias_default import sembrar_categorias_default


@pytest.fixture()
def client():
    """Cliente de pruebas con una BD SQLite en memoria, aislada por prueba."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def _fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    Testing = sessionmaker(bind=engine, autoflush=False)
    with Testing() as s:
        sembrar_categorias_default(s)

    def _get_db():
        with Testing() as s:
            yield s

    fastapi_app.dependency_overrides[get_db] = _get_db
    # Sin "with": no se dispara el lifespan que usaría la BD real
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.clear()
    engine.dispose()
