from datetime import date
from decimal import Decimal

import pytest

import app.api.deps as modulo_deps
from app.core.tiempo import rango_mes, sumar_meses


def cuenta_id(client, headers, nombre="Efectivo"):
    cuentas = client.get("/cuentas", headers=headers, params={"incluir_archivadas": True}).json()
    return next(c["id"] for c in cuentas if c["nombre"] == nombre)


def cat_id(client, headers, nombre):
    cats = client.get("/categorias", headers=headers).json()
    return next(c["id"] for c in cats if c["nombre"] == nombre)


def mov(client, headers, tipo, monto, fecha, categoria, cuenta=None):
    r = client.post("/transacciones", headers=headers, json={
        "tipo": tipo, "monto": str(monto), "fecha": fecha,
        "cuenta_id": cuenta or cuenta_id(client, headers), "categoria_id": cat_id(client, headers, categoria)})
    assert r.status_code == 201, r.text


def get(client, headers, ruta, **params):
    r = client.get(f"/resumen/{ruta}", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def D(x):
    return Decimal(str(x))


@pytest.fixture()
def datos(client, headers):
    """Octubre 2026: ingreso 2.500.000, gastos 100.000. Septiembre y otro usuario aparte."""
    mov(client, headers, "INGRESO", 2500000, "2026-10-01", "Salario")
    mov(client, headers, "GASTO", 18000, "2026-10-03", "Comida")
    mov(client, headers, "GASTO", 82000, "2026-10-31", "Transporte")  # último día del mes
    mov(client, headers, "GASTO", 999, "2026-09-30", "Comida")        # mes anterior
    mov(client, headers, "GASTO", 999, "2026-11-01", "Comida")        # mes siguiente
    # una transferencia no debe contar ni como ingreso ni como gasto
    banco = client.post("/cuentas", headers=headers,
                        json={"nombre": "Banco", "tipo": "BANCARIA", "saldo_inicial": "0"}).json()["id"]
    client.post("/transacciones", headers=headers, json={
        "tipo": "TRANSFERENCIA", "monto": "70000", "fecha": "2026-10-10",
        "cuenta_id": cuenta_id(client, headers), "cuenta_destino_id": banco})


# ---------- generales ----------

@pytest.mark.parametrize("ruta", ["mes", "por-categoria", "por-dia", "serie-mensual", "evolucion-balance"])
def test_requieren_autenticacion(client, ruta):
    assert client.get(f"/resumen/{ruta}").status_code == 401


@pytest.mark.parametrize("ruta", ["mes", "por-categoria", "por-dia", "serie-mensual", "evolucion-balance"])
@pytest.mark.parametrize("params", [{"mes": 13}, {"mes": 0}, {"anio": 1999, "mes": 1}, {"anio": 2026}, {"mes": 5}])
def test_periodo_invalido(client, headers, ruta, params):
    assert client.get(f"/resumen/{ruta}", headers=headers, params=params).status_code == 422


@pytest.mark.parametrize("ruta", ["serie-mensual", "evolucion-balance"])
@pytest.mark.parametrize("meses", [0, 25, -1])
def test_meses_fuera_de_rango(client, headers, ruta, meses):
    assert client.get(f"/resumen/{ruta}", headers=headers, params={"meses": meses}).status_code == 422


def test_sin_datos_todo_en_cero(client, headers):
    r = get(client, headers, "mes", anio=2026, mes=10)
    assert (D(r["ingresos"]), D(r["gastos"]), D(r["balance"])) == (0, 0, 0)
    assert get(client, headers, "por-categoria", anio=2026, mes=10) == []
    assert len(get(client, headers, "serie-mensual", meses=3, anio=2026, mes=10)) == 3


def test_sin_parametros_usa_el_mes_actual(client, headers, monkeypatch):
    monkeypatch.setattr(modulo_deps, "hoy", lambda: date(2026, 10, 15))
    mov(client, headers, "GASTO", 5000, "2026-10-02", "Comida")
    r = get(client, headers, "mes")
    assert (r["anio"], r["mes"], D(r["gastos"])) == (2026, 10, 5000)
    assert get(client, headers, "serie-mensual", meses=2)[-1]["mes"] == 10


def test_helpers_de_calendario():
    assert rango_mes(2026, 12) == (date(2026, 12, 1), date(2027, 1, 1))
    assert rango_mes(2026, 2) == (date(2026, 2, 1), date(2026, 3, 1))
    assert sumar_meses(2026, 2, -3) == (2025, 11)
    assert sumar_meses(2026, 12, 1) == (2027, 1)
    assert sumar_meses(2026, 1, -1) == (2025, 12)


# ---------- /resumen/mes ----------

def test_resumen_mes(client, headers, datos):
    r = get(client, headers, "mes", anio=2026, mes=10)
    assert D(r["ingresos"]) == 2500000
    assert D(r["gastos"]) == 100000  # incluye el 31, excluye 30/sep y 1/nov, ignora la transferencia
    assert D(r["balance"]) == 2400000


def test_resumen_mes_aislado_por_usuario(client, headers, headers_otro, datos):
    r = get(client, headers_otro, "mes", anio=2026, mes=10)
    assert D(r["ingresos"]) == D(r["gastos"]) == 0


# ---------- /resumen/por-categoria ----------

def test_por_categoria_con_porcentajes_y_orden(client, headers, datos):
    r = get(client, headers, "por-categoria", anio=2026, mes=10)
    assert [(c["categoria"], D(c["total"])) for c in r] == [("Transporte", 82000), ("Comida", 18000)]
    assert [D(c["porcentaje"]) for c in r] == [D("82.00"), D("18.00")]
    assert r[0]["color"] and r[0]["icono"]


def test_por_categoria_ingresos(client, headers, datos):
    r = get(client, headers, "por-categoria", anio=2026, mes=10, tipo="INGRESO")
    assert [(c["categoria"], D(c["porcentaje"])) for c in r] == [("Salario", D("100.00"))]


def test_subcategorias_se_suman_a_su_padre(client, headers):
    comida = cat_id(client, headers, "Comida")
    client.post("/categorias", headers=headers,
                json={"nombre": "Domicilios", "tipo": "GASTO", "categoria_padre_id": comida})
    mov(client, headers, "GASTO", 20000, "2026-10-02", "Comida")
    mov(client, headers, "GASTO", 10000, "2026-10-03", "Domicilios")
    mov(client, headers, "GASTO", 40000, "2026-10-04", "Transporte")

    agrupado = get(client, headers, "por-categoria", anio=2026, mes=10)
    assert [(c["categoria"], D(c["total"]), D(c["porcentaje"])) for c in agrupado] == [
        ("Transporte", 40000, D("57.14")), ("Comida", 30000, D("42.86"))]

    plano = get(client, headers, "por-categoria", anio=2026, mes=10, agrupar_subcategorias=False)
    assert {(c["categoria"], D(c["total"])) for c in plano} == {
        ("Transporte", 40000), ("Comida", 20000), ("Domicilios", 10000)}


def test_por_categoria_tipo_invalido(client, headers):
    assert client.get("/resumen/por-categoria", headers=headers, params={"tipo": "OTRO"}).status_code == 422


# ---------- /resumen/serie-mensual ----------

def test_serie_mensual_rellena_con_ceros_y_va_en_orden(client, headers, datos):
    r = get(client, headers, "serie-mensual", meses=3, anio=2026, mes=10)
    assert [(p["anio"], p["mes"]) for p in r] == [(2026, 8), (2026, 9), (2026, 10)]
    assert [D(p["gastos"]) for p in r] == [0, 999, 100000]
    assert [D(p["ingresos"]) for p in r] == [0, 0, 2500000]
    assert [D(p["balance"]) for p in r] == [0, -999, 2400000]


def test_serie_mensual_cruza_el_cambio_de_anio(client, headers):
    mov(client, headers, "GASTO", 1000, "2026-11-15", "Comida")
    mov(client, headers, "GASTO", 2000, "2026-12-31", "Comida")
    mov(client, headers, "GASTO", 3000, "2027-01-01", "Comida")
    mov(client, headers, "INGRESO", 4000, "2027-02-28", "Salario")
    r = get(client, headers, "serie-mensual", meses=4, anio=2027, mes=2)
    assert [(p["anio"], p["mes"]) for p in r] == [(2026, 11), (2026, 12), (2027, 1), (2027, 2)]
    assert [D(p["balance"]) for p in r] == [-1000, -2000, -3000, 4000]


def test_serie_mensual_por_defecto_son_6_meses(client, headers):
    assert len(get(client, headers, "serie-mensual", anio=2026, mes=10)) == 6


# ---------- /resumen/evolucion-balance ----------

def test_evolucion_balance_acumulada(client, headers):
    efectivo = cuenta_id(client, headers)
    client.patch(f"/cuentas/{efectivo}", headers=headers, json={"saldo_inicial": "100000"})
    nequi = client.post("/cuentas", headers=headers,
                        json={"nombre": "Nequi", "tipo": "BILLETERA_DIGITAL", "saldo_inicial": "50000"}).json()["id"]
    mov(client, headers, "INGRESO", 1000000, "2026-08-10", "Salario")
    mov(client, headers, "GASTO", 200000, "2026-09-05", "Comida")
    mov(client, headers, "GASTO", 50000, "2026-10-05", "Comida")
    mov(client, headers, "INGRESO", 300000, "2026-10-20", "Freelance", cuenta=nequi)
    client.post("/transacciones", headers=headers, json={
        "tipo": "TRANSFERENCIA", "monto": "10000", "fecha": "2026-10-12", "cuenta_id": efectivo, "cuenta_destino_id": nequi})

    completo = get(client, headers, "evolucion-balance", meses=3, anio=2026, mes=10)
    assert [(p["anio"], p["mes"], D(p["balance"])) for p in completo] == [
        (2026, 8, 1150000), (2026, 9, 950000), (2026, 10, 1200000)]

    # ventana más corta: lo anterior a la ventana entra como punto de partida
    corto = get(client, headers, "evolucion-balance", meses=2, anio=2026, mes=10)
    assert [D(p["balance"]) for p in corto] == [950000, 1200000]

    # el último punto coincide con la suma de los saldos de las cuentas
    total_cuentas = sum(D(c["saldo_actual"]) for c in client.get("/cuentas", headers=headers).json())
    assert D(completo[-1]["balance"]) == total_cuentas


def test_evolucion_balance_cuenta_archivada_sigue_sumando(client, headers):
    vieja = client.post("/cuentas", headers=headers,
                        json={"nombre": "Vieja", "tipo": "BANCARIA", "saldo_inicial": "70000"}).json()["id"]
    client.patch(f"/cuentas/{vieja}", headers=headers, json={"archivada": True})
    r = get(client, headers, "evolucion-balance", meses=1, anio=2026, mes=10)
    assert D(r[0]["balance"]) == 70000


# ---------- por día ----------

def test_por_dia_devuelve_todos_los_dias_del_mes(client, headers, datos):
    dias = get(client, headers, "por-dia", anio=2026, mes=10)
    assert len(dias) == 31
    assert [d["fecha"] for d in dias] == [f"2026-10-{n:02d}" for n in range(1, 32)]
    por_fecha = {d["fecha"]: d for d in dias}
    assert D(por_fecha["2026-10-01"]["ingresos"]) == 2500000 and D(por_fecha["2026-10-01"]["gastos"]) == 0
    assert D(por_fecha["2026-10-03"]["gastos"]) == 18000
    assert D(por_fecha["2026-10-31"]["gastos"]) == 82000  # último día incluido
    assert D(por_fecha["2026-10-10"]["gastos"]) == 0       # la transferencia no cuenta
    assert D(por_fecha["2026-10-10"]["ingresos"]) == 0


def test_por_dia_suma_lo_mismo_que_el_resumen_del_mes(client, headers, datos):
    dias = get(client, headers, "por-dia", anio=2026, mes=10)
    mes = get(client, headers, "mes", anio=2026, mes=10)
    assert sum(D(d["gastos"]) for d in dias) == D(mes["gastos"])
    assert sum(D(d["ingresos"]) for d in dias) == D(mes["ingresos"])


def test_por_dia_suma_varios_movimientos_del_mismo_dia(client, headers):
    mov(client, headers, "GASTO", 10000, "2026-02-05", "Comida")
    mov(client, headers, "GASTO", 5500, "2026-02-05", "Transporte")
    dias = get(client, headers, "por-dia", anio=2026, mes=2)
    assert len(dias) == 28
    assert D(dias[4]["gastos"]) == 15500


def test_por_dia_mes_bisiesto_y_aislado_por_usuario(client, headers, headers_otro):
    mov(client, headers, "GASTO", 1000, "2028-02-29", "Comida")
    assert len(get(client, headers, "por-dia", anio=2028, mes=2)) == 29
    otro = get(client, headers_otro, "por-dia", anio=2028, mes=2)
    assert all(D(d["gastos"]) == 0 for d in otro)


def test_por_dia_sin_parametros_usa_el_mes_actual(client, headers, monkeypatch):
    monkeypatch.setattr(modulo_deps, "hoy", lambda: date(2026, 11, 15))
    dias = get(client, headers, "por-dia")
    assert len(dias) == 30 and dias[0]["fecha"] == "2026-11-01"
