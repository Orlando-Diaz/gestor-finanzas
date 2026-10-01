import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.database import Base, get_db
from app.main import app as fastapi_app
from app.services.categorias_default import sembrar_categorias_default


@pytest.fixture()
def session_factory():
    """BD SQLite en memoria, aislada por prueba, con las categorías predeterminadas."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def _fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine, autoflush=False)
    with fabrica() as s:
        sembrar_categorias_default(s)
    yield fabrica
    engine.dispose()


@pytest.fixture()
def client(session_factory):
    def _get_db():
        with session_factory() as s:
            yield s

    fastapi_app.dependency_overrides[get_db] = _get_db
    # Sin "with": no se dispara el lifespan que usaría la BD real
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def db(session_factory):
    """Sesión directa a la BD de la prueba (para preparar o inspeccionar datos)."""
    with session_factory() as s:
        yield s


def _registrar_y_entrar(client, email: str) -> dict:
    datos = {"nombre": "Usuario", "email": email, "password": "clave-segura-1"}
    assert client.post("/auth/registro", json=datos).status_code == 201
    r = client.post("/auth/login", data={"username": email, "password": datos["password"]})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def headers(client):
    return _registrar_y_entrar(client, "uno@test.co")


@pytest.fixture()
def headers_otro(client):
    return _registrar_y_entrar(client, "dos@test.co")
