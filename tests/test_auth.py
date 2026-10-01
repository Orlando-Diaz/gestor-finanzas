from datetime import datetime, timedelta, timezone

import jwt
import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.config import Settings, settings
from app.core.security import ALGORITMO, crear_token, hashear_password, leer_token, verificar_password
from app.models import Categoria, TipoCategoria
from app.schemas.usuario import UsuarioCrear
from app.services.categorias_default import CATEGORIAS_DEFAULT, sembrar_categorias_default

REGISTRO = {"nombre": "Orlando", "email": "Orlando@Test.co", "password": "clave-segura-1"}


def registrar(client, **cambios):
    return client.post("/auth/registro", json={**REGISTRO, **cambios})


def login(client, email="orlando@test.co", password="clave-segura-1"):
    return client.post("/auth/login", data={"username": email, "password": password})


def test_registro_ok_normaliza_email_y_no_expone_password(client):
    r = registrar(client)
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["email"] == "orlando@test.co"
    assert cuerpo["moneda_por_defecto"] == "COP"
    assert "password" not in cuerpo and "password_hash" not in cuerpo


def test_registro_correo_duplicado_ignora_mayusculas(client):
    assert registrar(client).status_code == 201
    assert registrar(client, email="ORLANDO@test.co").status_code == 409


@pytest.mark.parametrize(
    "cambios",
    [{"password": "corta"}, {"email": "no-es-correo"}, {"nombre": "x"}, {"password": "ñ" * 40}],
)
def test_registro_datos_invalidos(client, cambios):
    assert registrar(client, **cambios).status_code == 422


def test_login_ok_y_me(client):
    registrar(client)
    r = login(client, email="ORLANDO@test.co")  # el correo no distingue mayúsculas
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["nombre"] == "Orlando"


def test_login_mismo_error_para_clave_mala_y_correo_inexistente(client):
    registrar(client)
    mala = login(client, password="otra-clave-123")
    inexistente = login(client, email="nadie@test.co")
    assert mala.status_code == inexistente.status_code == 401
    assert mala.json() == inexistente.json()


def test_me_sin_token_o_con_token_malo(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer basura"}).status_code == 401


def test_token_expirado_o_de_otra_firma_se_rechaza(client):
    registrar(client)
    ahora = datetime.now(timezone.utc)
    expirado = jwt.encode(
        {"sub": "1", "iat": ahora - timedelta(hours=2), "exp": ahora - timedelta(hours=1)},
        settings.secret_key,
        algorithm=ALGORITMO,
    )
    firma_ajena = jwt.encode({"sub": "1", "exp": ahora + timedelta(hours=1)}, "otra-clave-" * 4, algorithm=ALGORITMO)
    for t in (expirado, firma_ajena):
        assert client.get("/auth/me", headers={"Authorization": f"Bearer {t}"}).status_code == 401


def test_token_de_usuario_inexistente_se_rechaza(client):
    t = crear_token(9999)
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {t}"}).status_code == 401


def test_password_se_guarda_hasheada():
    h = hashear_password("clave-segura-1")
    assert h != "clave-segura-1" and verificar_password("clave-segura-1", h)
    assert not verificar_password("otra", h)
    assert leer_token(crear_token(7)) == 7 and leer_token("x") is None


def test_categorias_default_son_idempotentes(db):
    total = db.scalar(select(func.count()).select_from(Categoria))
    assert total == len(CATEGORIAS_DEFAULT)
    assert sembrar_categorias_default(db) == 0
    tipos = {c.tipo for c in db.scalars(select(Categoria))}
    assert tipos == {TipoCategoria.GASTO, TipoCategoria.INGRESO}


def test_usuario_nuevo_recibe_cuenta_efectivo(client, db):
    from app.models import Cuenta

    registrar(client)
    cuentas = db.scalars(select(Cuenta)).all()
    assert [c.nombre for c in cuentas] == ["Efectivo"]


def test_produccion_exige_secreto_seguro():
    with pytest.raises(ValidationError):
        Settings(entorno="produccion", secret_key="cambia-esto")
    Settings(entorno="produccion", secret_key="x" * 40)


def test_esquema_password_en_bytes():
    with pytest.raises(ValidationError):
        UsuarioCrear(nombre="Ana", email="a@b.co", password="ñ" * 40)  # 80 bytes
