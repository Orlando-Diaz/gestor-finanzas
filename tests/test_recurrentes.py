from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core import tiempo
from app.models import Frecuencia, Transaccion
from app.services.recurrentes import (
    fecha_quincenal_valida,
    procesar_recurrentes,
    siguiente_fecha,
)

S, Q, M, A = Frecuencia.SEMANAL, Frecuencia.QUINCENAL, Frecuencia.MENSUAL, Frecuencia.ANUAL


def D(x):
    return Decimal(str(x))


def hoy_es(monkeypatch, fecha: date):
    monkeypatch.setattr(tiempo, "hoy", lambda: fecha)


def cuenta_id(client, headers, nombre="Efectivo"):
    return next(c["id"] for c in client.get("/cuentas", headers=headers).json() if c["nombre"] == nombre)


def cat_id(client, headers, nombre):
    return next(c["id"] for c in client.get("/categorias", headers=headers).json() if c["nombre"] == nombre)


def crear(client, headers, inicio="2026-11-01", frecuencia="MENSUAL", tipo="GASTO", categoria=None, monto="800000", **extra):
    categoria = categoria or ("Salario" if tipo == "INGRESO" else "Arriendo")
    return client.post("/recurrentes", headers=headers, json={
        "tipo": tipo, "monto": monto, "cuenta_id": cuenta_id(client, headers),
        "categoria_id": cat_id(client, headers, categoria), "frecuencia": frecuencia,
        "proxima_fecha": inicio, **extra})


def movimientos(client, headers, **params):
    return client.get("/transacciones", headers=headers, params={"por_pagina": 100, **params}).json()["items"]


def saldo(client, headers, nombre="Efectivo"):
    return D(next(c["saldo_actual"] for c in client.get("/cuentas", headers=headers).json() if c["nombre"] == nombre))


# ---------- cálculo de fechas ----------

@pytest.mark.parametrize("frecuencia,actual,ancla,esperada", [
    (S, date(2026, 12, 28), 28, date(2027, 1, 4)),
    (Q, date(2026, 10, 15), 15, date(2026, 10, 31)),
    (Q, date(2026, 10, 31), 31, date(2026, 11, 15)),
    (Q, date(2026, 2, 28), 28, date(2026, 3, 15)),
    (Q, date(2026, 12, 31), 31, date(2027, 1, 15)),
    (M, date(2026, 1, 31), 31, date(2026, 2, 28)),
    (M, date(2026, 2, 28), 31, date(2026, 3, 31)),      # vuelve al 31 gracias al día ancla
    (M, date(2028, 1, 31), 31, date(2028, 2, 29)),      # año bisiesto
    (M, date(2026, 12, 15), 15, date(2027, 1, 15)),
    (A, date(2026, 6, 10), 10, date(2027, 6, 10)),
    (A, date(2027, 2, 28), 29, date(2028, 2, 29)),      # 29 de febrero vuelve en bisiesto
    (A, date(2028, 2, 29), 29, date(2029, 2, 28)),
])
def test_siguiente_fecha(frecuencia, actual, ancla, esperada):
    assert siguiente_fecha(frecuencia, actual, ancla) == esperada


def test_fecha_quincenal_valida():
    assert fecha_quincenal_valida(date(2026, 10, 15)) and fecha_quincenal_valida(date(2026, 10, 31))
    assert fecha_quincenal_valida(date(2026, 2, 28)) and fecha_quincenal_valida(date(2028, 2, 29))
    assert not fecha_quincenal_valida(date(2026, 10, 10)) and not fecha_quincenal_valida(date(2026, 2, 27))


# ---------- crear ----------

def test_requiere_autenticacion(client):
    assert client.get("/recurrentes").status_code == 401
    assert client.post("/recurrentes/procesar").status_code == 401


def test_crear_con_inicio_futuro_no_genera_nada(client, headers, monkeypatch):
    hoy_es(monkeypatch, date(2026, 10, 1))
    r = crear(client, headers, inicio="2026-11-01")
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["activa"] is True and cuerpo["proxima_fecha"] == "2026-11-01"
    assert cuerpo["cuenta"]["nombre"] == "Efectivo" and cuerpo["categoria"]["nombre"] == "Arriendo"
    assert movimientos(client, headers) == []


def test_crear_con_inicio_hoy_registra_el_primero_y_avanza(client, headers, db, monkeypatch):
    hoy_es(monkeypatch, date(2026, 10, 1))
    r = crear(client, headers, inicio="2026-10-01", nota="Arriendo apto")
    assert r.json()["proxima_fecha"] == "2026-11-01"
    movs = movimientos(client, headers)
    assert len(movs) == 1 and movs[0]["fecha"] == "2026-10-01" and movs[0]["nota"] == "Arriendo apto"
    assert D(movs[0]["monto"]) == 800000 and saldo(client, headers) == -800000
    assert db.scalar(select(Transaccion.recurrente_id)) == r.json()["id"]
    # y el usuario recibe el aviso
    n = client.get("/notificaciones", headers=headers).json()
    assert [x["tipo"] for x in n] == ["RECURRENTE_REGISTRADA"] and "$800.000" in n[0]["mensaje"]


def test_crear_con_inicio_pasado_registra_los_pendientes(client, headers, monkeypatch):
    hoy_es(monkeypatch, date(2026, 10, 15))
    r = crear(client, headers, inicio="2026-08-31")  # ancla 31
    assert r.json()["proxima_fecha"] == "2026-10-31"
    assert sorted(m["fecha"] for m in movimientos(client, headers)) == ["2026-08-31", "2026-09-30"]
    n = client.get("/notificaciones", headers=headers).json()
    assert "2 movimientos" in n[0]["mensaje"]


def test_ingreso_recurrente_suma(client, headers, monkeypatch):
    hoy_es(monkeypatch, date(2026, 10, 31))
    crear(client, headers, inicio="2026-10-15", frecuencia="QUINCENAL", tipo="INGRESO", monto="1500000")
    assert [m["fecha"] for m in movimientos(client, headers)] == ["2026-10-31", "2026-10-15"]
    assert saldo(client, headers) == 3000000


def test_semanal_con_fecha_fin_se_desactiva_sola(client, headers, monkeypatch):
    hoy_es(monkeypatch, date(2026, 12, 31))
    r = crear(client, headers, inicio="2026-10-01", frecuencia="SEMANAL", monto="1000", fecha_fin="2026-10-15").json()
    assert sorted(m["fecha"] for m in movimientos(client, headers)) == ["2026-10-01", "2026-10-08", "2026-10-15"]
    assert r["activa"] is False


def test_procesar_es_idempotente(client, headers, monkeypatch):
    hoy_es(monkeypatch, date(2026, 10, 1))
    crear(client, headers, inicio="2026-10-01")
    assert client.post("/recurrentes/procesar", headers=headers).json() == {"generadas": 0}
    hoy_es(monkeypatch, date(2026, 11, 1))
    assert client.post("/recurrentes/procesar", headers=headers).json() == {"generadas": 1}
    assert client.post("/recurrentes/procesar", headers=headers).json() == {"generadas": 0}
    assert len(movimientos(client, headers)) == 2


def test_un_gasto_recurrente_dispara_alertas_de_presupuesto(client, headers, monkeypatch):
    hoy_es(monkeypatch, date(2026, 10, 1))
    client.post("/presupuestos", headers=headers, json={
        "categoria_id": cat_id(client, headers, "Arriendo"), "monto_limite": "800000", "mes": 10, "anio": 2026})
    crear(client, headers, inicio="2026-10-01", monto="800000")
    tipos = {n["tipo"] for n in client.get("/notificaciones", headers=headers).json()}
    assert tipos == {"PRESUPUESTO_UMBRAL", "RECURRENTE_REGISTRADA"}  # 100% justo: umbral, no exceso


def test_procesar_solo_toca_al_usuario_o_a_todos(client, headers, headers_otro, db, monkeypatch):
    hoy_es(monkeypatch, date(2026, 9, 1))
    crear(client, headers, inicio="2026-10-01")
    crear(client, headers_otro, inicio="2026-10-01")
    hoy_es(monkeypatch, date(2026, 10, 1))
    assert client.post("/recurrentes/procesar", headers=headers).json() == {"generadas": 1}
    assert len(movimientos(client, headers_otro)) == 0
    assert procesar_recurrentes(db) == 1  # a todos: queda el otro usuario
    assert len(movimientos(client, headers_otro)) == 1


def test_si_ya_hay_un_movimiento_ese_dia_no_se_duplica_ni_se_atasca(client, headers, db, monkeypatch):
    hoy_es(monkeypatch, date(2026, 9, 1))
    r = crear(client, headers, inicio="2026-10-01").json()
    db.add(Transaccion(usuario_id=1, cuenta_id=cuenta_id(client, headers), categoria_id=cat_id(client, headers, "Arriendo"),
                       recurrente_id=r["id"], tipo="GASTO", monto=Decimal("1"), fecha=date(2026, 10, 1)))
    db.commit()
    hoy_es(monkeypatch, date(2026, 10, 15))
    assert client.post("/recurrentes/procesar", headers=headers).json() == {"generadas": 0}
    assert client.get(f"/recurrentes/{r['id']}", headers=headers).json()["proxima_fecha"] == "2026-11-01"  # avanzó
    assert len(movimientos(client, headers)) == 1


def test_no_se_puede_mover_un_movimiento_generado_a_una_fecha_ya_generada(client, headers, monkeypatch):
    hoy_es(monkeypatch, date(2026, 11, 15))
    crear(client, headers, inicio="2026-10-01")
    movs = movimientos(client, headers)
    r = client.patch(f"/transacciones/{movs[0]['id']}", headers=headers, json={"fecha": movs[1]["fecha"]})
    assert r.status_code == 409


# ---------- validaciones ----------

@pytest.mark.parametrize("cambios", [
    {"tipo": "TRANSFERENCIA"},
    {"monto": "0"}, {"monto": "-1"},
    {"frecuencia": "DIARIA"},
    {"frecuencia": "QUINCENAL", "inicio": "2026-11-10"},
    {"fecha_fin": "2026-10-31"},                         # anterior al inicio
    {"inicio": "no-es-fecha"},
])
def test_datos_invalidos(client, headers, cambios):
    inicio = cambios.pop("inicio", "2026-11-01")
    assert crear(client, headers, inicio=inicio, **cambios).status_code == 422


def test_referencias_invalidas(client, headers, headers_otro):
    ajena = client.post("/cuentas", headers=headers_otro, json={"nombre": "Ajena", "tipo": "BANCARIA"}).json()["id"]
    base = {"tipo": "GASTO", "monto": "10", "frecuencia": "MENSUAL", "proxima_fecha": "2026-11-01",
            "cuenta_id": cuenta_id(client, headers), "categoria_id": cat_id(client, headers, "Arriendo")}
    post = lambda **c: client.post("/recurrentes", headers=headers, json={**base, **c}).status_code
    assert post(cuenta_id=ajena) == 422
    assert post(cuenta_id=99999) == 422
    assert post(categoria_id=cat_id(client, headers, "Salario")) == 422   # categoría de otro tipo
    assert post(categoria_id=99999) == 422
    vieja = client.post("/cuentas", headers=headers, json={"nombre": "Vieja", "tipo": "BANCARIA"}).json()["id"]
    client.patch(f"/cuentas/{vieja}", headers=headers, json={"archivada": True})
    assert post(cuenta_id=vieja) == 422


# ---------- listar / editar / borrar ----------

def test_listado_ordenado_y_filtro(client, headers, monkeypatch):
    hoy_es(monkeypatch, date(2026, 10, 1))
    crear(client, headers, inicio="2026-12-01", nota="B")
    crear(client, headers, inicio="2026-11-01", nota="A")
    pausada = crear(client, headers, inicio="2026-10-20", nota="C").json()["id"]
    client.patch(f"/recurrentes/{pausada}", headers=headers, json={"activa": False})
    todas = client.get("/recurrentes", headers=headers).json()
    assert [r["nota"] for r in todas] == ["A", "B", "C"]  # activas primero, por fecha
    assert [r["nota"] for r in client.get("/recurrentes", headers=headers, params={"solo_activas": True}).json()] == ["A", "B"]


def test_editar_el_monto_solo_afecta_a_lo_futuro(client, headers, monkeypatch):
    hoy_es(monkeypatch, date(2026, 10, 1))
    rid = crear(client, headers, inicio="2026-10-01", monto="800000").json()["id"]
    assert client.patch(f"/recurrentes/{rid}", headers=headers, json={"monto": "850000"}).status_code == 200
    hoy_es(monkeypatch, date(2026, 11, 1))
    client.post("/recurrentes/procesar", headers=headers)
    assert sorted(D(m["monto"]) for m in movimientos(client, headers)) == [800000, 850000]


def test_pausar_y_reactivar(client, headers, monkeypatch):
    hoy_es(monkeypatch, date(2026, 10, 1))
    rid = crear(client, headers, inicio="2026-10-01").json()["id"]
    client.patch(f"/recurrentes/{rid}", headers=headers, json={"activa": False})
    hoy_es(monkeypatch, date(2027, 2, 1))
    assert client.post("/recurrentes/procesar", headers=headers).json() == {"generadas": 0}  # pausada: nada
    # reactivarla con la fecha vieja registraría meses de golpe: se exige una fecha nueva
    assert client.patch(f"/recurrentes/{rid}", headers=headers, json={"activa": True}).status_code == 422
    r = client.patch(f"/recurrentes/{rid}", headers=headers, json={"activa": True, "proxima_fecha": "2027-03-05"})
    assert r.status_code == 200 and r.json()["activa"] is True and len(movimientos(client, headers)) == 1


def test_cambiar_la_fecha_actualiza_el_dia_ancla(client, headers, monkeypatch):
    hoy_es(monkeypatch, date(2026, 10, 1))
    rid = crear(client, headers, inicio="2026-11-30").json()["id"]
    client.patch(f"/recurrentes/{rid}", headers=headers, json={"proxima_fecha": "2026-11-10"})
    hoy_es(monkeypatch, date(2027, 1, 20))
    client.post("/recurrentes/procesar", headers=headers)
    assert sorted(m["fecha"] for m in movimientos(client, headers)) == ["2026-11-10", "2026-12-10", "2027-01-10"]


def test_quitar_fecha_fin_con_null(client, headers, monkeypatch):
    hoy_es(monkeypatch, date(2026, 10, 1))
    rid = crear(client, headers, inicio="2026-11-01", fecha_fin="2026-12-01").json()["id"]
    r = client.patch(f"/recurrentes/{rid}", headers=headers, json={"fecha_fin": None})
    assert r.status_code == 200 and r.json()["fecha_fin"] is None


def test_editar_rechaza_cambios_invalidos(client, headers, headers_otro, monkeypatch):
    hoy_es(monkeypatch, date(2026, 10, 1))
    rid = crear(client, headers, inicio="2026-11-01").json()["id"]
    ajena = client.post("/cuentas", headers=headers_otro, json={"nombre": "Ajena", "tipo": "BANCARIA"}).json()["id"]
    invalidos = [
        {"monto": None}, {"monto": "0"}, {"cuenta_id": None}, {"categoria_id": None}, {"frecuencia": None},
        {"proxima_fecha": None}, {"activa": None}, {"cuenta_id": ajena},
        {"categoria_id": cat_id(client, headers, "Salario")}, {"frecuencia": "QUINCENAL"},  # 1 de nov no es 15 ni fin de mes
        {"fecha_fin": "2026-10-01"}, {"tipo": "INGRESO"},
    ]
    for cuerpo in invalidos:
        assert client.patch(f"/recurrentes/{rid}", headers=headers, json=cuerpo).status_code == 422, cuerpo
    assert client.patch(f"/recurrentes/{rid}", headers=headers, json={"frecuencia": "QUINCENAL", "proxima_fecha": "2026-11-15"}).status_code == 200


def test_borrar_conserva_el_historial(client, headers, db, monkeypatch):
    hoy_es(monkeypatch, date(2026, 10, 1))
    rid = crear(client, headers, inicio="2026-10-01").json()["id"]
    assert client.delete(f"/recurrentes/{rid}", headers=headers).status_code == 204
    assert client.get(f"/recurrentes/{rid}", headers=headers).status_code == 404
    assert len(movimientos(client, headers)) == 1
    assert db.scalar(select(Transaccion.recurrente_id)) is None
    # y la cuenta ya no tiene recurrentes que la bloqueen (sí tiene movimientos)
    assert client.delete(f"/cuentas/{cuenta_id(client, headers)}", headers=headers).status_code == 409


def test_aislamiento_entre_usuarios(client, headers, headers_otro, monkeypatch):
    hoy_es(monkeypatch, date(2026, 10, 1))
    rid = crear(client, headers_otro, inicio="2026-11-01").json()["id"]
    assert client.get("/recurrentes", headers=headers).json() == []
    assert client.get(f"/recurrentes/{rid}", headers=headers).status_code == 404
    assert client.patch(f"/recurrentes/{rid}", headers=headers, json={"nota": "x"}).status_code == 404
    assert client.delete(f"/recurrentes/{rid}", headers=headers).status_code == 404
