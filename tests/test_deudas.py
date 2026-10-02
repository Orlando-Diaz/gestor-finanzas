from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import Deuda, PagoDeuda, TipoDeuda


def D(x):
    return Decimal(str(x))


@pytest.fixture()
def hoy(monkeypatch):
    monkeypatch.setattr("app.core.tiempo.hoy", lambda: date(2026, 10, 15))
    return date(2026, 10, 15)


def crear(client, headers, persona="Juan", total=100000, tipo="ME_DEBEN", **extra):
    r = client.post("/deudas", headers=headers, json={"tipo": tipo, "persona": persona, "monto_total": str(total), **extra})
    assert r.status_code == 201, r.text
    return r.json()


def pagar(client, headers, deuda_id, monto, **extra):
    return client.post(f"/deudas/{deuda_id}/pagos", headers=headers, json={"monto": str(monto), **extra})


@pytest.mark.parametrize("metodo, ruta", [
    ("get", "/deudas"), ("get", "/deudas/resumen"), ("post", "/deudas"), ("get", "/deudas/1"),
    ("patch", "/deudas/1"), ("delete", "/deudas/1"), ("post", "/deudas/1/pagos"), ("delete", "/deudas/1/pagos/1"),
])
def test_requieren_autenticacion(client, metodo, ruta):
    assert getattr(client, metodo)(ruta).status_code == 401


# ---------- crear ----------

def test_crear_deuda_usa_hoy_por_defecto(client, headers, hoy):
    d = crear(client, headers, descripcion="para el arriendo")
    assert d["fecha"] == "2026-10-15" and D(d["pendiente"]) == 100000 and D(d["pagado"]) == 0
    assert d["saldada"] is False and d["vencida"] is False and d["pagos"] == []


@pytest.mark.parametrize("cuerpo", [
    {"tipo": "ME_DEBEN", "persona": "", "monto_total": "10"},
    {"tipo": "ME_DEBEN", "persona": "Ana", "monto_total": "0"},
    {"tipo": "OTRO", "persona": "Ana", "monto_total": "10"},
    {"persona": "Ana", "monto_total": "10"},
    {"tipo": "DEBO", "persona": "Ana", "monto_total": "10", "fecha": "2026-10-10", "fecha_vencimiento": "2026-10-09"},
])
def test_deuda_invalida(client, headers, cuerpo):
    assert client.post("/deudas", headers=headers, json=cuerpo).status_code == 422


def test_vencimiento_anterior_a_hoy_cuando_no_se_envia_fecha(client, headers, hoy):
    r = client.post("/deudas", headers=headers, json={"tipo": "DEBO", "persona": "Ana", "monto_total": "10", "fecha_vencimiento": "2026-10-01"})
    assert r.status_code == 422


# ---------- pagos ----------

def test_los_pagos_reducen_lo_pendiente_hasta_saldar(client, headers, hoy):
    deuda = crear(client, headers, total=100000)
    d = pagar(client, headers, deuda["id"], 30000, nota="primer abono").json()
    assert (D(d["pagado"]), D(d["pendiente"]), D(d["porcentaje"]), d["saldada"]) == (30000, 70000, 30, False)
    d = pagar(client, headers, deuda["id"], 70000, fecha="2026-10-20").json()
    assert D(d["pendiente"]) == 0 and d["saldada"] is True and D(d["porcentaje"]) == 100
    assert [p["fecha"] for p in d["pagos"]] == ["2026-10-20", "2026-10-15"]


def test_no_se_puede_pagar_mas_de_lo_que_falta(client, headers, hoy):
    deuda = crear(client, headers, total=100000)
    pagar(client, headers, deuda["id"], 90000)
    assert pagar(client, headers, deuda["id"], 10001).status_code == 422
    assert pagar(client, headers, deuda["id"], 10000).status_code == 201


@pytest.mark.parametrize("monto", [0, -5])
def test_pago_con_monto_invalido(client, headers, monto):
    deuda = crear(client, headers)
    assert pagar(client, headers, deuda["id"], monto).status_code == 422


def test_borrar_un_pago_devuelve_el_saldo(client, headers, hoy):
    deuda = crear(client, headers, total=100000)
    pago_id = pagar(client, headers, deuda["id"], 100000).json()["pagos"][0]["id"]
    assert client.get(f"/deudas/{deuda['id']}", headers=headers).json()["saldada"] is True
    assert client.delete(f"/deudas/{deuda['id']}/pagos/{pago_id}", headers=headers).status_code == 204
    d = client.get(f"/deudas/{deuda['id']}", headers=headers).json()
    assert d["saldada"] is False and D(d["pendiente"]) == 100000
    assert client.delete(f"/deudas/{deuda['id']}/pagos/{pago_id}", headers=headers).status_code == 404


def test_un_pago_no_se_borra_desde_otra_deuda(client, headers, hoy):
    una = crear(client, headers, persona="A")
    otra = crear(client, headers, persona="B")
    pago_id = pagar(client, headers, una["id"], 100).json()["pagos"][0]["id"]
    assert client.delete(f"/deudas/{otra['id']}/pagos/{pago_id}", headers=headers).status_code == 404


# ---------- vencimiento ----------

def test_vencida_solo_si_hay_saldo_y_paso_la_fecha(client, headers, hoy):
    futura = crear(client, headers, persona="futura", fecha_vencimiento="2026-10-16")
    hoy_mismo = crear(client, headers, persona="hoy", fecha_vencimiento="2026-10-15")
    vencida = crear(client, headers, persona="vencida", fecha="2026-09-01", fecha_vencimiento="2026-10-14")
    pagada = crear(client, headers, persona="pagada", total=10, fecha="2026-09-01", fecha_vencimiento="2026-10-01")
    pagar(client, headers, pagada["id"], 10)
    estado = {d["persona"]: d["vencida"] for d in client.get("/deudas", headers=headers, params={"estado": "todas"}).json()}
    assert estado == {"futura": False, "hoy": False, "vencida": True, "pagada": False}


# ---------- listar ----------

def test_filtros_y_orden(client, headers, hoy):
    sin_venc = crear(client, headers, persona="sin vencimiento")
    tarde = crear(client, headers, persona="tarde", fecha_vencimiento="2026-12-01")
    pronto = crear(client, headers, persona="pronto", fecha_vencimiento="2026-10-20")
    mia = crear(client, headers, persona="mi deuda", tipo="DEBO")
    saldada = crear(client, headers, persona="saldada", total=5)
    pagar(client, headers, saldada["id"], 5)

    def nombres(**p):
        return [d["persona"] for d in client.get("/deudas", headers=headers, params=p).json()]

    # los que vencen antes primero; sin vencimiento al final (y entre ellos, la más reciente arriba)
    assert nombres() == ["pronto", "tarde", "mi deuda", "sin vencimiento"]
    assert nombres(estado="saldadas") == ["saldada"]
    assert len(nombres(estado="todas")) == 5
    assert nombres(tipo="DEBO") == ["mi deuda"]
    assert client.get("/deudas", headers=headers, params={"estado": "raro"}).status_code == 422


# ---------- resumen ----------

def test_resumen_suma_solo_lo_pendiente(client, headers, hoy):
    a = crear(client, headers, persona="a", total=100000)
    crear(client, headers, persona="b", total=50000, fecha="2026-09-01", fecha_vencimiento="2026-10-01")
    pagar(client, headers, a["id"], 40000)
    c = crear(client, headers, persona="c", total=30000, tipo="DEBO")
    saldada = crear(client, headers, persona="d", total=999, tipo="DEBO")
    pagar(client, headers, saldada["id"], 999)
    r = client.get("/deudas/resumen", headers=headers).json()
    assert D(r["me_deben"]) == 110000 and D(r["debo"]) == 30000 and D(r["neto"]) == 80000
    assert (r["cantidad_me_deben"], r["cantidad_debo"], r["vencidas"]) == (2, 1, 1)


def test_resumen_vacio(client, headers):
    r = client.get("/deudas/resumen", headers=headers).json()
    assert D(r["me_deben"]) == D(r["debo"]) == D(r["neto"]) == 0 and r["vencidas"] == 0


# ---------- editar y borrar ----------

def test_editar_deuda(client, headers, hoy):
    deuda = crear(client, headers, total=100000, fecha_vencimiento="2026-11-01")
    pagar(client, headers, deuda["id"], 60000)
    d = client.patch(f"/deudas/{deuda['id']}", headers=headers,
                     json={"persona": "Juan P.", "monto_total": "150000", "fecha_vencimiento": None}).json()
    assert d["persona"] == "Juan P." and D(d["pendiente"]) == 90000 and d["fecha_vencimiento"] is None


@pytest.mark.parametrize("cuerpo", [
    {"monto_total": "50000"},          # menos de lo ya pagado (60.000)
    {"persona": None}, {"monto_total": None}, {"monto_total": "0"},
    {"fecha_vencimiento": "2026-10-01"},  # antes de la fecha de la deuda (15/oct)
    {"tipo": "DEBO"},                  # el tipo no se cambia
])
def test_editar_con_datos_invalidos(client, headers, hoy, cuerpo):
    deuda = crear(client, headers, total=100000)
    pagar(client, headers, deuda["id"], 60000)
    assert client.patch(f"/deudas/{deuda['id']}", headers=headers, json=cuerpo).status_code == 422


def test_borrar_deuda_borra_sus_pagos(client, headers, db, hoy):
    deuda = crear(client, headers)
    pagar(client, headers, deuda["id"], 1000)
    assert client.delete(f"/deudas/{deuda['id']}", headers=headers).status_code == 204
    assert client.get(f"/deudas/{deuda['id']}", headers=headers).status_code == 404
    assert db.scalar(select(func.count()).select_from(PagoDeuda)) == 0


# ---------- aislamiento, borrado de cuenta y restricciones ----------

def test_otro_usuario_no_ve_ni_toca_mis_deudas(client, headers, headers_otro, hoy):
    deuda = crear(client, headers)
    pago_id = pagar(client, headers, deuda["id"], 100).json()["pagos"][0]["id"]
    assert client.get("/deudas", headers=headers_otro, params={"estado": "todas"}).json() == []
    assert D(client.get("/deudas/resumen", headers=headers_otro).json()["me_deben"]) == 0
    for metodo, ruta, cuerpo in [
        ("get", f"/deudas/{deuda['id']}", None),
        ("patch", f"/deudas/{deuda['id']}", {"persona": "x"}),
        ("delete", f"/deudas/{deuda['id']}", None),
        ("post", f"/deudas/{deuda['id']}/pagos", {"monto": "1"}),
        ("delete", f"/deudas/{deuda['id']}/pagos/{pago_id}", None),
    ]:
        r = getattr(client, metodo)(ruta, headers=headers_otro, **({"json": cuerpo} if cuerpo else {}))
        assert r.status_code == 404, (metodo, ruta)


def test_eliminar_la_cuenta_borra_las_deudas(client, headers, db, hoy):
    deuda = crear(client, headers)
    pagar(client, headers, deuda["id"], 1000)
    assert client.post("/auth/eliminar-cuenta", headers=headers, json={"password": "clave-segura-1"}).status_code == 204
    assert db.scalar(select(func.count()).select_from(Deuda)) == 0
    assert db.scalar(select(func.count()).select_from(PagoDeuda)) == 0


def test_la_base_rechaza_montos_invalidos(client, headers, db, hoy):
    deuda = crear(client, headers)
    db.add(PagoDeuda(deuda_id=deuda["id"], monto=Decimal("0"), fecha=hoy))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    uid = db.scalar(select(Deuda.usuario_id).where(Deuda.id == deuda["id"]))
    db.add(Deuda(usuario_id=uid, tipo=TipoDeuda.DEBO, persona="x", monto_total=Decimal("10"),
                 fecha=date(2026, 10, 10), fecha_vencimiento=date(2026, 10, 9)))
    with pytest.raises(IntegrityError):
        db.commit()
