from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import Categoria, TipoTransaccion, Transaccion, TransaccionRecurrente, Frecuencia


def crear(client, headers, **datos):
    base = {"nombre": "Nequi", "tipo": "BILLETERA_DIGITAL", "saldo_inicial": "200000"}
    return client.post("/cuentas", json={**base, **datos}, headers=headers)


def por_nombre(client, headers, nombre, **params):
    cuentas = client.get("/cuentas", headers=headers, params=params).json()
    return next(c for c in cuentas if c["nombre"] == nombre)


def mi_id(client, headers):
    return client.get("/auth/me", headers=headers).json()["id"]


def categoria_gasto(db):
    return db.scalar(select(Categoria).where(Categoria.nombre == "Comida"))


def test_requiere_autenticacion(client):
    assert client.get("/cuentas").status_code == 401
    assert client.post("/cuentas", json={}).status_code == 401


def test_usuario_nuevo_ve_su_cuenta_efectivo_con_saldo_cero(client, headers):
    cuentas = client.get("/cuentas", headers=headers).json()
    assert [(c["nombre"], c["saldo_actual"]) for c in cuentas] == [("Efectivo", "0.00")]


def test_crear_cuenta_y_saldo_inicial(client, headers):
    r = crear(client, headers)
    assert r.status_code == 201
    assert Decimal(r.json()["saldo_actual"]) == Decimal("200000")


def test_nombre_duplicado_sin_importar_mayusculas(client, headers):
    assert crear(client, headers).status_code == 201
    assert crear(client, headers, nombre="  NEQUI ").status_code == 409
    assert crear(client, headers, nombre="Efectivo").status_code == 409


def test_datos_invalidos(client, headers):
    assert crear(client, headers, nombre="   ").status_code == 422
    assert crear(client, headers, tipo="CRIPTO").status_code == 422
    assert crear(client, headers, saldo_inicial="1.234").status_code == 422


def test_saldo_calculado_con_gastos_ingresos_y_transferencias(client, headers, db):
    """Ejemplo de la conversación: almuerzo en efectivo y retiro del cajero."""
    uid = mi_id(client, headers)
    efectivo = por_nombre(client, headers, "Efectivo")
    efectivo_id = efectivo["id"]
    client.patch(f"/cuentas/{efectivo_id}", json={"saldo_inicial": "50000"}, headers=headers)
    banco = crear(client, headers, nombre="Bancolombia", tipo="BANCARIA", saldo_inicial="1500000").json()
    nequi = crear(client, headers).json()
    comida = categoria_gasto(db)

    db.add_all([
        Transaccion(usuario_id=uid, cuenta_id=efectivo_id, categoria_id=comida.id,
                    tipo=TipoTransaccion.GASTO, monto=Decimal("18000"), fecha=date(2026, 10, 1)),
        Transaccion(usuario_id=uid, cuenta_id=banco["id"], cuenta_destino_id=efectivo_id,
                    tipo=TipoTransaccion.TRANSFERENCIA, monto=Decimal("100000"), fecha=date(2026, 10, 1)),
        Transaccion(usuario_id=uid, cuenta_id=nequi["id"], categoria_id=comida.id,
                    tipo=TipoTransaccion.INGRESO, monto=Decimal("35000.50"), fecha=date(2026, 10, 1)),
    ])
    db.commit()

    saldos = {c["nombre"]: Decimal(c["saldo_actual"]) for c in client.get("/cuentas", headers=headers).json()}
    assert saldos == {
        "Efectivo": Decimal("132000.00"),   # 50.000 - 18.000 + 100.000
        "Bancolombia": Decimal("1400000.00"),
        "Nequi": Decimal("235000.50"),
    }
    uno = client.get(f"/cuentas/{efectivo_id}", headers=headers).json()
    assert Decimal(uno["saldo_actual"]) == Decimal("132000.00")


def test_no_se_ven_ni_tocan_cuentas_de_otro_usuario(client, headers, headers_otro):
    ajena = crear(client, headers_otro, nombre="Secreta").json()
    assert all(c["nombre"] != "Secreta" for c in client.get("/cuentas", headers=headers).json())
    assert client.get(f"/cuentas/{ajena['id']}", headers=headers).status_code == 404
    assert client.patch(f"/cuentas/{ajena['id']}", json={"nombre": "x"}, headers=headers).status_code == 404
    assert client.delete(f"/cuentas/{ajena['id']}", headers=headers).status_code == 404
    # y el mismo nombre se puede repetir entre usuarios distintos
    assert crear(client, headers, nombre="Secreta").status_code == 201


def test_actualizar_y_archivar(client, headers):
    cuenta = crear(client, headers).json()
    r = client.patch(f"/cuentas/{cuenta['id']}", json={"nombre": "Nequi personal", "archivada": True}, headers=headers)
    assert r.status_code == 200 and r.json()["archivada"] is True
    assert all(c["id"] != cuenta["id"] for c in client.get("/cuentas", headers=headers).json())
    todas = client.get("/cuentas", headers=headers, params={"incluir_archivadas": True}).json()
    assert any(c["id"] == cuenta["id"] for c in todas)


def test_actualizar_rechaza_nulos_y_nombre_repetido(client, headers):
    cuenta = crear(client, headers).json()
    assert client.patch(f"/cuentas/{cuenta['id']}", json={"nombre": None}, headers=headers).status_code == 422
    assert client.patch(f"/cuentas/{cuenta['id']}", json={"nombre": "efectivo"}, headers=headers).status_code == 409
    # renombrar a su propio nombre (cambiando mayúsculas) es válido
    assert client.patch(f"/cuentas/{cuenta['id']}", json={"nombre": "NEQUI"}, headers=headers).status_code == 200


def test_borrar_sin_movimientos_si_con_movimientos_no(client, headers, db):
    libre = crear(client, headers, nombre="Libre").json()
    assert client.delete(f"/cuentas/{libre['id']}", headers=headers).status_code == 204
    assert client.get(f"/cuentas/{libre['id']}", headers=headers).status_code == 404

    uid = mi_id(client, headers)
    usada = crear(client, headers, nombre="Usada").json()
    db.add(Transaccion(usuario_id=uid, cuenta_id=usada["id"], categoria_id=categoria_gasto(db).id,
                       tipo=TipoTransaccion.GASTO, monto=Decimal("10"), fecha=date(2026, 10, 1)))
    db.commit()
    assert client.delete(f"/cuentas/{usada['id']}", headers=headers).status_code == 409

    # cuenta destino de una transferencia también cuenta como uso
    destino = crear(client, headers, nombre="Destino").json()
    db.add(Transaccion(usuario_id=uid, cuenta_id=usada["id"], cuenta_destino_id=destino["id"],
                       tipo=TipoTransaccion.TRANSFERENCIA, monto=Decimal("5"), fecha=date(2026, 10, 1)))
    db.commit()
    assert client.delete(f"/cuentas/{destino['id']}", headers=headers).status_code == 409


def test_cuenta_con_recurrente_no_se_borra(client, headers, db):
    uid = mi_id(client, headers)
    cuenta = crear(client, headers, nombre="ConRecurrente").json()
    db.add(TransaccionRecurrente(usuario_id=uid, cuenta_id=cuenta["id"], categoria_id=categoria_gasto(db).id,
                                 tipo=TipoTransaccion.GASTO, monto=Decimal("1"), frecuencia=Frecuencia.MENSUAL,
                                 proxima_fecha=date(2026, 11, 1), dia_ancla=1))
    db.commit()
    assert client.delete(f"/cuentas/{cuenta['id']}", headers=headers).status_code == 409
