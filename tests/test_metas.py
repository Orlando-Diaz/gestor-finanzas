from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models import AporteMeta, Meta


def D(x):
    return Decimal(str(x))


@pytest.fixture()
def hoy(monkeypatch):
    """Fija "hoy" en el 15 de octubre de 2026."""
    monkeypatch.setattr("app.core.tiempo.hoy", lambda: date(2026, 10, 15))
    return date(2026, 10, 15)


def crear(client, headers, nombre="Viaje a Cartagena", objetivo=1000000, **extra):
    r = client.post("/metas", headers=headers, json={"nombre": nombre, "monto_objetivo": str(objetivo), **extra})
    assert r.status_code == 201, r.text
    return r.json()


def aportar(client, headers, meta_id, monto, tipo="APORTE", **extra):
    return client.post(f"/metas/{meta_id}/aportes", headers=headers, json={"tipo": tipo, "monto": str(monto), **extra})


# ---------- acceso ----------

@pytest.mark.parametrize("metodo, ruta", [
    ("get", "/metas"), ("post", "/metas"), ("get", "/metas/1"), ("patch", "/metas/1"), ("delete", "/metas/1"),
    ("post", "/metas/1/aportes"), ("delete", "/metas/1/aportes/1"),
])
def test_requieren_autenticacion(client, metodo, ruta):
    assert getattr(client, metodo)(ruta).status_code == 401


# ---------- crear y validar ----------

def test_crear_meta_empieza_en_cero(client, headers, hoy):
    m = crear(client, headers, icono="✈️", color="#2A9D8F")
    assert (D(m["ahorrado"]), D(m["faltante"]), D(m["porcentaje"])) == (0, 1000000, 0)
    assert m["cumplida"] is False and m["aportes"] == [] and m["cuota_mensual_sugerida"] is None


@pytest.mark.parametrize("cuerpo", [
    {"nombre": "", "monto_objetivo": "100"},
    {"nombre": "x", "monto_objetivo": "0"},
    {"nombre": "x", "monto_objetivo": "-5"},
    {"nombre": "x", "monto_objetivo": "100", "color": "verde"},
    {"nombre": "x"},
])
def test_meta_invalida(client, headers, cuerpo):
    assert client.post("/metas", headers=headers, json=cuerpo).status_code == 422


# ---------- aportes y progreso ----------

def test_aportes_y_retiros_calculan_el_progreso(client, headers, hoy):
    meta = crear(client, headers)
    assert aportar(client, headers, meta["id"], 300000).status_code == 201
    assert aportar(client, headers, meta["id"], 200000).status_code == 201
    r = aportar(client, headers, meta["id"], 50000, tipo="RETIRO")
    assert r.status_code == 201
    m = r.json()
    assert D(m["ahorrado"]) == 450000 and D(m["faltante"]) == 550000 and D(m["porcentaje"]) == 45
    assert m["cumplida"] is False
    assert len(m["aportes"]) == 3


def test_aporte_usa_hoy_por_defecto_y_los_recientes_van_primero(client, headers, hoy):
    meta = crear(client, headers)
    aportar(client, headers, meta["id"], 1000, fecha="2026-09-01", nota="viejo")
    m = aportar(client, headers, meta["id"], 2000).json()
    assert [a["fecha"] for a in m["aportes"]] == ["2026-10-15", "2026-09-01"]


def test_no_se_puede_retirar_mas_de_lo_ahorrado(client, headers, hoy):
    meta = crear(client, headers)
    aportar(client, headers, meta["id"], 1000)
    assert aportar(client, headers, meta["id"], 1001, tipo="RETIRO").status_code == 422
    assert aportar(client, headers, meta["id"], 1000, tipo="RETIRO").status_code == 201  # justo todo


@pytest.mark.parametrize("monto", [0, -1])
def test_aporte_con_monto_invalido(client, headers, monto):
    meta = crear(client, headers)
    assert aportar(client, headers, meta["id"], monto).status_code == 422


def test_borrar_aporte_no_puede_dejar_saldo_negativo(client, headers, hoy):
    meta = crear(client, headers)
    m = aportar(client, headers, meta["id"], 1000).json()
    aporte_id = m["aportes"][0]["id"]
    m = aportar(client, headers, meta["id"], 400, tipo="RETIRO").json()
    retiro_id = m["aportes"][0]["id"]
    # borrar el aporte dejaría -400
    assert client.delete(f"/metas/{meta['id']}/aportes/{aporte_id}", headers=headers).status_code == 422
    # borrar el retiro devuelve la plata a la meta
    assert client.delete(f"/metas/{meta['id']}/aportes/{retiro_id}", headers=headers).status_code == 204
    assert D(client.get(f"/metas/{meta['id']}", headers=headers).json()["ahorrado"]) == 1000
    assert client.delete(f"/metas/{meta['id']}/aportes/{aporte_id}", headers=headers).status_code == 204
    assert client.delete(f"/metas/{meta['id']}/aportes/{aporte_id}", headers=headers).status_code == 404


# ---------- meta cumplida ----------

def test_meta_cumplida_avisa_una_sola_vez(client, headers, hoy):
    meta = crear(client, headers, nombre="Moto", objetivo=500000)
    aportar(client, headers, meta["id"], 400000)
    assert client.get("/notificaciones/conteo", headers=headers).json()["no_leidas"] == 0
    m = aportar(client, headers, meta["id"], 100000).json()
    assert m["cumplida"] is True and D(m["faltante"]) == 0
    avisos = client.get("/notificaciones", headers=headers).json()
    assert len(avisos) == 1 and "Moto" in avisos[0]["mensaje"] and "$500.000" in avisos[0]["mensaje"]
    aportar(client, headers, meta["id"], 50000)  # ahorrar de más no repite el aviso
    assert len(client.get("/notificaciones", headers=headers).json()) == 1
    assert D(client.get(f"/metas/{meta['id']}", headers=headers).json()["porcentaje"]) == 110


def test_retirar_y_volver_a_cumplir_avisa_de_nuevo(client, headers, hoy):
    meta = crear(client, headers, objetivo=1000)
    aportar(client, headers, meta["id"], 1000)
    aportar(client, headers, meta["id"], 500, tipo="RETIRO")  # vuelve a estar en curso
    aportar(client, headers, meta["id"], 500)                 # la cumple otra vez
    assert len(client.get("/notificaciones", headers=headers).json()) == 2


def test_bajar_el_objetivo_puede_cumplir_la_meta(client, headers, hoy):
    meta = crear(client, headers, objetivo=1000000)
    aportar(client, headers, meta["id"], 600000)
    m = client.patch(f"/metas/{meta['id']}", headers=headers, json={"monto_objetivo": "600000"}).json()
    assert m["cumplida"] is True
    assert len(client.get("/notificaciones", headers=headers).json()) == 1


# ---------- cuota sugerida ----------

def test_cuota_mensual_sugerida(client, headers, hoy):
    meta = crear(client, headers, objetivo=1000000, fecha_objetivo="2027-01-31")
    m = aportar(client, headers, meta["id"], 400000).json()
    # faltan 600.000 y quedan 3 meses (nov, dic, ene)
    assert D(m["cuota_mensual_sugerida"]) == 200000


def test_sin_cuota_si_no_hay_fecha_si_ya_paso_o_si_se_cumplio(client, headers, hoy):
    assert crear(client, headers, nombre="a")["cuota_mensual_sugerida"] is None
    assert crear(client, headers, nombre="b", fecha_objetivo="2026-09-01")["cuota_mensual_sugerida"] is None
    meta = crear(client, headers, nombre="c", objetivo=100, fecha_objetivo="2027-01-01")
    assert aportar(client, headers, meta["id"], 100).json()["cuota_mensual_sugerida"] is None


def test_la_cuota_de_este_mismo_mes_es_todo_lo_que_falta(client, headers, hoy):
    m = crear(client, headers, objetivo=90000, fecha_objetivo="2026-10-31")
    assert D(m["cuota_mensual_sugerida"]) == 90000


# ---------- editar, archivar, borrar ----------

def test_editar_y_quitar_la_fecha(client, headers, hoy):
    meta = crear(client, headers, fecha_objetivo="2027-05-01")
    m = client.patch(f"/metas/{meta['id']}", headers=headers, json={"nombre": "Otro nombre", "fecha_objetivo": None}).json()
    assert m["nombre"] == "Otro nombre" and m["fecha_objetivo"] is None


@pytest.mark.parametrize("cuerpo", [{"nombre": None}, {"monto_objetivo": None}, {"archivada": None}, {"monto_objetivo": "0"}, {"raro": 1}])
def test_editar_con_datos_invalidos(client, headers, cuerpo):
    meta = crear(client, headers)
    assert client.patch(f"/metas/{meta['id']}", headers=headers, json=cuerpo).status_code == 422


def test_archivar_oculta_la_meta(client, headers):
    meta = crear(client, headers)
    client.patch(f"/metas/{meta['id']}", headers=headers, json={"archivada": True})
    assert client.get("/metas", headers=headers).json() == []
    visibles = client.get("/metas", headers=headers, params={"incluir_archivadas": True}).json()
    assert [m["id"] for m in visibles] == [meta["id"]]


def test_borrar_meta_borra_sus_aportes(client, headers, db, hoy):
    meta = crear(client, headers)
    aportar(client, headers, meta["id"], 5000)
    assert client.delete(f"/metas/{meta['id']}", headers=headers).status_code == 204
    assert client.get(f"/metas/{meta['id']}", headers=headers).status_code == 404
    assert db.scalar(select(func.count()).select_from(AporteMeta)) == 0


def test_orden_en_curso_primero_las_cumplidas_al_final(client, headers, hoy):
    sin_fecha = crear(client, headers, nombre="sin fecha")
    lejana = crear(client, headers, nombre="lejana", fecha_objetivo="2028-01-01")
    cercana = crear(client, headers, nombre="cercana", fecha_objetivo="2026-12-01")
    lista = crear(client, headers, nombre="lista", objetivo=100)
    aportar(client, headers, lista["id"], 100)
    orden = [m["nombre"] for m in client.get("/metas", headers=headers).json()]
    assert orden == ["cercana", "lejana", "sin fecha", "lista"]


# ---------- aislamiento y borrado de cuenta ----------

def test_otro_usuario_no_ve_ni_toca_mis_metas(client, headers, headers_otro, hoy):
    meta = crear(client, headers)
    aporte_id = aportar(client, headers, meta["id"], 1000).json()["aportes"][0]["id"]
    assert client.get("/metas", headers=headers_otro).json() == []
    for metodo, ruta, cuerpo in [
        ("get", f"/metas/{meta['id']}", None),
        ("patch", f"/metas/{meta['id']}", {"nombre": "robada"}),
        ("delete", f"/metas/{meta['id']}", None),
        ("post", f"/metas/{meta['id']}/aportes", {"monto": "1"}),
        ("delete", f"/metas/{meta['id']}/aportes/{aporte_id}", None),
    ]:
        r = getattr(client, metodo)(ruta, headers=headers_otro, **({"json": cuerpo} if cuerpo else {}))
        assert r.status_code == 404, (metodo, ruta)
    assert D(client.get(f"/metas/{meta['id']}", headers=headers).json()["ahorrado"]) == 1000


def test_eliminar_la_cuenta_borra_las_metas(client, headers, db, hoy):
    meta = crear(client, headers)
    aportar(client, headers, meta["id"], 5000)
    r = client.post("/auth/eliminar-cuenta", headers=headers, json={"password": "clave-segura-1"})
    assert r.status_code == 204
    assert db.scalar(select(func.count()).select_from(Meta)) == 0
    assert db.scalar(select(func.count()).select_from(AporteMeta)) == 0
