from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core import tiempo
from app.models import (
    Categoria,
    Cuenta,
    Deuda,
    Meta,
    Notificacion,
    Presupuesto,
    Transaccion,
    TransaccionRecurrente,
    Usuario,
)
from app.services import arranque
from app.services.arranque import tareas_de_arranque
from app.services.categorias_default import CATEGORIAS_DEFAULT

CLAVE = "clave-segura-1"


def entrar(client, email="uno@test.co", password=CLAVE):
    r = client.post("/auth/login", data={"username": email, "password": password})
    return r


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def cuenta_id(client, headers, nombre="Efectivo"):
    return next(c["id"] for c in client.get("/cuentas", headers=headers).json() if c["nombre"] == nombre)


def cat_id(client, headers, nombre):
    return next(c["id"] for c in client.get("/categorias", headers=headers).json() if c["nombre"] == nombre)


# ---------- editar perfil ----------

def test_cambiar_nombre(client, headers):
    r = client.patch("/auth/me", headers=headers, json={"nombre": "  Orlando Díaz  "})
    assert r.status_code == 200 and r.json()["nombre"] == "Orlando Díaz"
    assert client.get("/auth/me", headers=headers).json()["nombre"] == "Orlando Díaz"


@pytest.mark.parametrize("cuerpo", [{"nombre": "x"}, {"nombre": "   "}, {}, {"nombre": "Ana", "email": "otro@test.co"}, {"nombre": "Ana", "activo": False}])
def test_perfil_solo_admite_el_nombre(client, headers, cuerpo):
    assert client.patch("/auth/me", headers=headers, json=cuerpo).status_code == 422


def test_perfil_requiere_autenticacion(client):
    assert client.patch("/auth/me", json={"nombre": "Ana"}).status_code == 401
    assert client.post("/auth/cambiar-password", json={}).status_code == 401
    assert client.post("/auth/eliminar-cuenta", json={}).status_code == 401


# ---------- cambiar contraseña ----------

def test_cambiar_password_invalida_las_sesiones_anteriores(client, headers):
    r = client.post("/auth/cambiar-password", headers=headers, json={"password_actual": CLAVE, "password_nueva": "otra-clave-99"})
    assert r.status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 401      # el token viejo ya no sirve
    assert entrar(client).status_code == 401                                # ni la clave vieja
    nuevo = entrar(client, password="otra-clave-99")
    assert nuevo.status_code == 200
    assert client.get("/auth/me", headers=auth(nuevo.json()["access_token"])).status_code == 200


def test_cambiar_password_validaciones(client, headers):
    def cambiar(actual, nueva):
        return client.post("/auth/cambiar-password", headers=headers, json={"password_actual": actual, "password_nueva": nueva})

    assert cambiar("incorrecta-1", "otra-clave-99").status_code == 400
    assert cambiar(CLAVE, CLAVE).status_code == 422          # igual a la actual
    assert cambiar(CLAVE, "corta").status_code == 422
    assert cambiar(CLAVE, "ñ" * 40).status_code == 422        # más de 72 bytes
    assert client.get("/auth/me", headers=headers).status_code == 200   # nada cambió


def test_cambiar_password_no_afecta_a_otros(client, headers, headers_otro):
    client.post("/auth/cambiar-password", headers=headers, json={"password_actual": CLAVE, "password_nueva": "otra-clave-99"})
    assert client.get("/auth/me", headers=headers_otro).status_code == 200


# ---------- eliminar cuenta ----------

def poblar(client, headers):
    """Un usuario con datos en todas las tablas."""
    efectivo = cuenta_id(client, headers)
    banco = client.post("/cuentas", headers=headers, json={"nombre": "Banco", "tipo": "BANCARIA", "saldo_inicial": "1000"}).json()["id"]
    comida = cat_id(client, headers, "Comida")
    client.post("/categorias", headers=headers, json={"nombre": "Domicilios", "tipo": "GASTO", "categoria_padre_id": comida})
    client.post("/transacciones", headers=headers, json={"tipo": "GASTO", "monto": "90000", "fecha": "2026-10-02", "cuenta_id": efectivo, "categoria_id": comida})
    client.post("/transacciones", headers=headers, json={"tipo": "TRANSFERENCIA", "monto": "10", "fecha": "2026-10-03", "cuenta_id": banco, "cuenta_destino_id": efectivo})
    client.post("/presupuestos", headers=headers, json={"categoria_id": comida, "monto_limite": "100000", "mes": 10, "anio": 2026})
    client.post("/recurrentes", headers=headers, json={
        "tipo": "GASTO", "monto": "800000", "cuenta_id": efectivo, "categoria_id": cat_id(client, headers, "Arriendo"),
        "frecuencia": "MENSUAL", "proxima_fecha": "2026-10-01"})
    meta = client.post("/metas", headers=headers, json={"nombre": "Viaje", "monto_objetivo": "500000"}).json()["id"]
    client.post(f"/metas/{meta}/aportes", headers=headers, json={"tipo": "APORTE", "monto": "100000"})
    deuda = client.post("/deudas", headers=headers, json={"tipo": "ME_DEBEN", "persona": "Carlos", "monto_total": "200000"}).json()["id"]
    client.post(f"/deudas/{deuda}/pagos", headers=headers, json={"monto": "50000"})


def contar(db, modelo, uid):
    return db.scalar(select(func.count()).select_from(modelo).where(modelo.usuario_id == uid))


def test_eliminar_cuenta_borra_todo_lo_del_usuario_y_nada_mas(client, headers, headers_otro, db, monkeypatch):
    monkeypatch.setattr(tiempo, "hoy", lambda: date(2026, 10, 5))
    poblar(client, headers)
    poblar(client, headers_otro)
    uid = client.get("/auth/me", headers=headers).json()["id"]
    otro = client.get("/auth/me", headers=headers_otro).json()["id"]
    for modelo in (Cuenta, Transaccion, Presupuesto, Notificacion, TransaccionRecurrente, Categoria, Meta, Deuda):
        assert contar(db, modelo, uid) > 0, modelo  # el escenario sí llena cada tabla

    assert client.post("/auth/eliminar-cuenta", headers=headers, json={"password": CLAVE}).status_code == 204

    db.expire_all()
    assert db.get(Usuario, uid) is None
    for modelo in (Cuenta, Transaccion, Presupuesto, Notificacion, TransaccionRecurrente, Categoria, Meta, Deuda):
        assert contar(db, modelo, uid) == 0, modelo
    # el otro usuario y las categorías predeterminadas siguen intactos
    assert db.get(Usuario, otro) is not None
    for modelo in (Cuenta, Transaccion, Presupuesto, Notificacion, TransaccionRecurrente, Categoria, Meta, Deuda):
        assert contar(db, modelo, otro) > 0, modelo
    assert db.scalar(select(func.count()).select_from(Categoria).where(Categoria.usuario_id.is_(None))) == len(CATEGORIAS_DEFAULT)
    # y el acceso desaparece
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert entrar(client).status_code == 401


def test_eliminar_cuenta_exige_la_contrasena_correcta(client, headers, db):
    assert client.post("/auth/eliminar-cuenta", headers=headers, json={"password": "incorrecta-1"}).status_code == 400
    assert client.post("/auth/eliminar-cuenta", headers=headers, json={}).status_code == 422
    assert client.get("/auth/me", headers=headers).status_code == 200
    assert db.scalar(select(func.count()).select_from(Usuario)) == 1


def test_se_puede_registrar_de_nuevo_con_el_mismo_correo(client, headers):
    client.post("/auth/eliminar-cuenta", headers=headers, json={"password": CLAVE})
    r = client.post("/auth/registro", json={"nombre": "Nuevo", "email": "uno@test.co", "password": CLAVE})
    assert r.status_code == 201
    token = entrar(client).json()["access_token"]
    assert [c["nombre"] for c in client.get("/cuentas", headers=auth(token)).json()] == ["Efectivo"]  # empieza limpio


# ---------- recurrentes al iniciar sesión y al arrancar ----------

def crear_recurrente(client, headers, inicio):
    r = client.post("/recurrentes", headers=headers, json={
        "tipo": "GASTO", "monto": "800000", "cuenta_id": cuenta_id(client, headers),
        "categoria_id": cat_id(client, headers, "Arriendo"), "frecuencia": "MENSUAL", "proxima_fecha": inicio})
    assert r.status_code == 201


def movimientos(client, headers):
    return client.get("/transacciones", headers=headers).json()["total"]


def test_al_iniciar_sesion_se_registran_las_recurrentes_vencidas(client, headers, monkeypatch):
    monkeypatch.setattr(tiempo, "hoy", lambda: date(2026, 10, 1))
    crear_recurrente(client, headers, "2026-11-01")
    assert movimientos(client, headers) == 0
    monkeypatch.setattr(tiempo, "hoy", lambda: date(2026, 11, 2))
    token = entrar(client).json()["access_token"]          # el simple hecho de entrar las registra
    assert movimientos(client, auth(token)) == 1


def test_un_fallo_procesando_recurrentes_no_impide_entrar(client, headers, monkeypatch):
    import app.api.auth as modulo_auth

    def falla(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(modulo_auth, "procesar_recurrentes", falla)
    assert entrar(client).status_code == 200


def test_al_arrancar_se_siembran_categorias_y_se_procesan_recurrentes_de_todos(client, headers, headers_otro, db, monkeypatch):
    monkeypatch.setattr(tiempo, "hoy", lambda: date(2026, 10, 1))
    crear_recurrente(client, headers, "2026-11-01")
    crear_recurrente(client, headers_otro, "2026-11-01")
    db.query(Categoria).filter(Categoria.usuario_id.is_(None), Categoria.nombre == "Mascotas").delete()
    db.commit()

    monkeypatch.setattr(tiempo, "hoy", lambda: date(2026, 11, 1))
    tareas_de_arranque(db)
    assert movimientos(client, headers) == 1 and movimientos(client, headers_otro) == 1
    assert db.scalar(select(func.count()).select_from(Categoria).where(Categoria.usuario_id.is_(None))) == len(CATEGORIAS_DEFAULT)
    tareas_de_arranque(db)  # idempotente
    assert movimientos(client, headers) == 1


def test_un_fallo_al_arrancar_no_tumba_la_app(db, monkeypatch):
    def falla(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(arranque, "procesar_recurrentes", falla)
    tareas_de_arranque(db)  # no debe lanzar
