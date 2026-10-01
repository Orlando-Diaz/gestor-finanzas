from decimal import Decimal

import pytest


def D(x):
    return Decimal(str(x))


def cuenta_id(client, headers, nombre="Efectivo"):
    return next(c["id"] for c in client.get("/cuentas", headers=headers).json() if c["nombre"] == nombre)


def cat_id(client, headers, nombre):
    return next(c["id"] for c in client.get("/categorias", headers=headers).json() if c["nombre"] == nombre)


def gasto(client, headers, monto, categoria="Comida", fecha="2026-10-05"):
    r = client.post("/transacciones", headers=headers, json={
        "tipo": "GASTO", "monto": str(monto), "fecha": fecha,
        "cuenta_id": cuenta_id(client, headers), "categoria_id": cat_id(client, headers, categoria)})
    assert r.status_code == 201, r.text
    return r.json()


def crear(client, headers, categoria="Comida", limite="100000", mes=10, anio=2026, **extra):
    return client.post("/presupuestos", headers=headers, json={
        "categoria_id": cat_id(client, headers, categoria), "monto_limite": str(limite),
        "mes": mes, "anio": anio, **extra})


def listar(client, headers, mes=10, anio=2026):
    r = client.get("/presupuestos", headers=headers, params={"mes": mes, "anio": anio})
    assert r.status_code == 200, r.text
    return r.json()


def notifs(client, headers, **params):
    return client.get("/notificaciones", headers=headers, params=params).json()


# ---------- CRUD ----------

def test_requiere_autenticacion(client):
    assert client.get("/presupuestos").status_code == 401
    assert client.post("/presupuestos", json={}).status_code == 401


def test_crear_y_ver_progreso(client, headers):
    r = crear(client, headers, limite="100000")
    assert r.status_code == 201
    p = r.json()
    assert p["categoria"]["nombre"] == "Comida" and p["umbral_alerta"] == 80
    assert (D(p["gastado"]), D(p["restante"]), D(p["porcentaje"]), p["estado"]) == (0, 100000, 0, "OK")

    gasto(client, headers, 30000)
    p = client.get(f"/presupuestos/{p['id']}", headers=headers).json()
    assert (D(p["gastado"]), D(p["restante"]), D(p["porcentaje"]), p["estado"]) == (30000, 70000, 30, "OK")


def test_estados_ok_alerta_excedido(client, headers):
    pid = crear(client, headers, limite="100000").json()["id"]
    estado = lambda: client.get(f"/presupuestos/{pid}", headers=headers).json()
    gasto(client, headers, 79999)
    assert estado()["estado"] == "OK"        # 79,999% todavía no llega al umbral
    gasto(client, headers, 1)
    assert estado()["estado"] == "ALERTA"    # justo 80%
    gasto(client, headers, 20000)
    assert estado()["estado"] == "ALERTA"    # justo 100% no es exceso
    gasto(client, headers, 1)
    e = estado()
    assert e["estado"] == "EXCEDIDO" and D(e["restante"]) == -1


def test_solo_cuenta_gastos_del_mes_y_de_la_categoria(client, headers):
    crear(client, headers, limite="100000")
    gasto(client, headers, 10000, fecha="2026-10-31")
    gasto(client, headers, 5000, fecha="2026-09-30")             # mes anterior
    gasto(client, headers, 7000, fecha="2026-11-01")             # mes siguiente
    gasto(client, headers, 9000, categoria="Transporte")         # otra categoría
    client.post("/transacciones", headers=headers, json={        # los ingresos no cuentan
        "tipo": "INGRESO", "monto": "50000", "fecha": "2026-10-05",
        "cuenta_id": cuenta_id(client, headers), "categoria_id": cat_id(client, headers, "Salario")})
    assert D(listar(client, headers)[0]["gastado"]) == 10000


def test_el_presupuesto_del_padre_incluye_subcategorias(client, headers):
    comida = cat_id(client, headers, "Comida")
    client.post("/categorias", headers=headers, json={"nombre": "Domicilios", "tipo": "GASTO", "categoria_padre_id": comida})
    crear(client, headers, "Comida", "100000")
    crear(client, headers, "Domicilios", "20000")
    gasto(client, headers, 15000, categoria="Domicilios")
    gasto(client, headers, 10000, categoria="Comida")
    por_cat = {p["categoria"]["nombre"]: D(p["gastado"]) for p in listar(client, headers)}
    assert por_cat == {"Comida": 25000, "Domicilios": 15000}


def test_listado_por_mes_y_ordenado(client, headers):
    crear(client, headers, "Transporte")
    crear(client, headers, "Comida")
    crear(client, headers, "Comida", mes=11)
    assert [p["categoria"]["nombre"] for p in listar(client, headers)] == ["Comida", "Transporte"]
    assert len(listar(client, headers, mes=11)) == 1
    assert listar(client, headers, mes=12) == []


def test_validaciones_al_crear(client, headers, headers_otro):
    assert crear(client, headers).status_code == 201
    assert crear(client, headers).status_code == 409                       # mismo mes y categoría
    assert crear(client, headers, mes=11).status_code == 201               # otro mes sí
    assert crear(client, headers, "Salario").status_code == 422            # categoría de ingreso
    for cuerpo in ({"limite": "0"}, {"limite": "-5"}, {"mes": 13}, {"mes": 0}, {"anio": 1999}, {"umbral_alerta": 0}, {"umbral_alerta": 101}):
        assert crear(client, headers, categoria="Transporte", **cuerpo).status_code == 422, cuerpo
    assert client.post("/presupuestos", headers=headers, json={"categoria_id": 99999, "monto_limite": "5", "mes": 1, "anio": 2026}).status_code == 422
    ajena = client.post("/categorias", headers=headers_otro, json={"nombre": "Ajena", "tipo": "GASTO"}).json()
    assert client.post("/presupuestos", headers=headers, json={"categoria_id": ajena["id"], "monto_limite": "5", "mes": 1, "anio": 2026}).status_code == 422


def test_categoria_archivada_no_admite_presupuesto(client, headers):
    propia = client.post("/categorias", headers=headers, json={"nombre": "Vieja", "tipo": "GASTO"}).json()
    client.patch(f"/categorias/{propia['id']}", headers=headers, json={"archivada": True})
    r = client.post("/presupuestos", headers=headers, json={"categoria_id": propia["id"], "monto_limite": "5", "mes": 1, "anio": 2026})
    assert r.status_code == 422


def test_aislamiento_entre_usuarios(client, headers, headers_otro):
    pid = crear(client, headers_otro).json()["id"]
    assert listar(client, headers) == []
    assert client.get(f"/presupuestos/{pid}", headers=headers).status_code == 404
    assert client.patch(f"/presupuestos/{pid}", headers=headers, json={"monto_limite": "1"}).status_code == 404
    assert client.delete(f"/presupuestos/{pid}", headers=headers).status_code == 404
    assert crear(client, headers).status_code == 201  # y el mismo mes/categoría no choca entre usuarios


def test_editar_y_borrar(client, headers):
    pid = crear(client, headers, limite="100000").json()["id"]
    r = client.patch(f"/presupuestos/{pid}", headers=headers, json={"monto_limite": "250000", "umbral_alerta": 90})
    assert r.status_code == 200 and D(r.json()["monto_limite"]) == 250000 and r.json()["umbral_alerta"] == 90
    for malo in ({"monto_limite": None}, {"monto_limite": "0"}, {"umbral_alerta": 0}, {"categoria_id": 3}, {"mes": 5}):
        assert client.patch(f"/presupuestos/{pid}", headers=headers, json=malo).status_code == 422, malo
    assert client.delete(f"/presupuestos/{pid}", headers=headers).status_code == 204
    assert client.get(f"/presupuestos/{pid}", headers=headers).status_code == 404


# ---------- copiar ----------

def test_copiar_presupuestos_de_un_mes_a_otro(client, headers):
    crear(client, headers, "Comida", "100000", umbral_alerta=70)
    crear(client, headers, "Transporte", "50000")
    crear(client, headers, "Comida", "999", mes=11)  # ya existe en el destino: se respeta
    r = client.post("/presupuestos/copiar", headers=headers,
                    json={"desde_anio": 2026, "desde_mes": 10, "a_anio": 2026, "a_mes": 11})
    assert r.status_code == 201
    assert [p["categoria"]["nombre"] for p in r.json()] == ["Transporte"]
    noviembre = {p["categoria"]["nombre"]: p for p in listar(client, headers, mes=11)}
    assert D(noviembre["Comida"]["monto_limite"]) == 999 and D(noviembre["Transporte"]["monto_limite"]) == 50000
    # copiar de nuevo no duplica nada
    assert client.post("/presupuestos/copiar", headers=headers,
                       json={"desde_anio": 2026, "desde_mes": 10, "a_anio": 2026, "a_mes": 11}).json() == []


def test_copiar_cruza_de_anio_y_conserva_umbral(client, headers):
    crear(client, headers, "Comida", "100000", mes=12, umbral_alerta=65)
    r = client.post("/presupuestos/copiar", headers=headers,
                    json={"desde_anio": 2026, "desde_mes": 12, "a_anio": 2027, "a_mes": 1}).json()
    assert (r[0]["anio"], r[0]["mes"], r[0]["umbral_alerta"]) == (2027, 1, 65)


def test_copiar_errores(client, headers):
    base = {"desde_anio": 2026, "desde_mes": 10, "a_anio": 2026, "a_mes": 11}
    assert client.post("/presupuestos/copiar", headers=headers, json=base).status_code == 404  # origen vacío
    crear(client, headers)
    assert client.post("/presupuestos/copiar", headers=headers, json={**base, "a_mes": 10}).status_code == 422
    assert client.post("/presupuestos/copiar", headers=headers, json={**base, "a_mes": 13}).status_code == 422


# ---------- alertas ----------

def test_alerta_de_umbral_se_envia_una_sola_vez(client, headers):
    crear(client, headers, "Comida", "100000")
    gasto(client, headers, 50000)
    assert notifs(client, headers) == []
    gasto(client, headers, 35000)                                   # 85%
    n = notifs(client, headers)
    assert len(n) == 1 and n[0]["tipo"] == "PRESUPUESTO_UMBRAL" and n[0]["leida"] is False
    assert "85%" in n[0]["mensaje"] and "Comida" in n[0]["mensaje"] and "$85.000" in n[0]["mensaje"] and "$100.000" in n[0]["mensaje"]
    assert "oct 2026" in n[0]["mensaje"]
    gasto(client, headers, 5000)                                    # 90%: no repite
    assert len(notifs(client, headers)) == 1


def test_alerta_de_exceso_y_no_vuelve_la_de_umbral(client, headers):
    crear(client, headers, "Comida", "100000")
    gasto(client, headers, 85000)
    gasto(client, headers, 30000)                                   # 115%
    tipos = [n["tipo"] for n in notifs(client, headers)]
    assert tipos == ["PRESUPUESTO_EXCEDIDO", "PRESUPUESTO_UMBRAL"]
    gasto(client, headers, 1000)
    assert len(notifs(client, headers)) == 2


def test_saltar_directo_al_exceso_solo_avisa_del_exceso(client, headers):
    crear(client, headers, "Comida", "100000")
    gasto(client, headers, 120000)
    assert [n["tipo"] for n in notifs(client, headers)] == ["PRESUPUESTO_EXCEDIDO"]


def test_gasto_en_subcategoria_alerta_al_presupuesto_del_padre(client, headers):
    comida = cat_id(client, headers, "Comida")
    client.post("/categorias", headers=headers, json={"nombre": "Domicilios", "tipo": "GASTO", "categoria_padre_id": comida})
    crear(client, headers, "Comida", "100000")
    gasto(client, headers, 90000, categoria="Domicilios")
    n = notifs(client, headers)
    assert len(n) == 1 and "Comida" in n[0]["mensaje"]


def test_crear_presupuesto_ya_excedido_avisa_de_inmediato(client, headers):
    gasto(client, headers, 60000)
    crear(client, headers, "Comida", "50000")
    assert [n["tipo"] for n in notifs(client, headers)] == ["PRESUPUESTO_EXCEDIDO"]


def test_los_gastos_de_otros_meses_o_categorias_no_disparan_alertas(client, headers):
    crear(client, headers, "Comida", "100000")
    gasto(client, headers, 99000, fecha="2026-09-15")
    gasto(client, headers, 99000, categoria="Transporte")
    assert notifs(client, headers) == []


def test_editar_un_gasto_tambien_evalua(client, headers):
    crear(client, headers, "Comida", "100000")
    g = gasto(client, headers, 10000)
    client.patch(f"/transacciones/{g['id']}", headers=headers, json={"monto": "95000"})
    assert [n["tipo"] for n in notifs(client, headers)] == ["PRESUPUESTO_UMBRAL"]


def test_cambiar_el_limite_reinicia_las_alertas(client, headers):
    pid = crear(client, headers, "Comida", "100000").json()["id"]
    gasto(client, headers, 90000)
    assert len(notifs(client, headers)) == 1
    # límite más alto: ya no hay alerta, y la anterior se retira
    client.patch(f"/presupuestos/{pid}", headers=headers, json={"monto_limite": "1000000"})
    assert notifs(client, headers) == []
    # y puede volver a dispararse
    gasto(client, headers, 800000)
    assert [n["tipo"] for n in notifs(client, headers)] == ["PRESUPUESTO_UMBRAL"]


def test_borrar_presupuesto_conserva_la_notificacion(client, headers):
    pid = crear(client, headers, "Comida", "100000").json()["id"]
    gasto(client, headers, 90000)
    assert client.delete(f"/presupuestos/{pid}", headers=headers).status_code == 204
    n = notifs(client, headers)
    assert len(n) == 1 and n[0]["presupuesto_id"] is None


def test_las_alertas_son_de_cada_usuario(client, headers, headers_otro):
    crear(client, headers, "Comida", "100000")
    gasto(client, headers, 90000)
    assert len(notifs(client, headers)) == 1 and notifs(client, headers_otro) == []


# ---------- /notificaciones ----------

@pytest.fixture()
def con_alertas(client, headers):
    crear(client, headers, "Comida", "100000")
    crear(client, headers, "Transporte", "100000")
    gasto(client, headers, 90000, "Comida")
    gasto(client, headers, 120000, "Transporte")


def test_notificaciones_requieren_autenticacion(client):
    for ruta in ("/notificaciones", "/notificaciones/conteo"):
        assert client.get(ruta).status_code == 401
    assert client.post("/notificaciones/leer-todas").status_code == 401


def test_conteo_orden_y_marcar_leidas(client, headers, con_alertas):
    assert client.get("/notificaciones/conteo", headers=headers).json() == {"no_leidas": 2}
    lista = notifs(client, headers)
    assert [n["tipo"] for n in lista] == ["PRESUPUESTO_EXCEDIDO", "PRESUPUESTO_UMBRAL"]  # la más reciente primero

    r = client.patch(f"/notificaciones/{lista[0]['id']}/leer", headers=headers)
    assert r.status_code == 200 and r.json()["leida"] is True
    assert client.get("/notificaciones/conteo", headers=headers).json() == {"no_leidas": 1}
    assert len(notifs(client, headers, solo_no_leidas=True)) == 1

    assert client.post("/notificaciones/leer-todas", headers=headers).status_code == 204
    assert client.get("/notificaciones/conteo", headers=headers).json() == {"no_leidas": 0}
    assert notifs(client, headers, solo_no_leidas=True) == []
    assert len(notifs(client, headers)) == 2  # siguen en el historial


def test_limite_del_listado(client, headers, con_alertas):
    assert len(notifs(client, headers, limite=1)) == 1
    assert client.get("/notificaciones", headers=headers, params={"limite": 0}).status_code == 422
    assert client.get("/notificaciones", headers=headers, params={"limite": 201}).status_code == 422


def test_borrar_notificacion(client, headers, con_alertas):
    nid = notifs(client, headers)[0]["id"]
    assert client.delete(f"/notificaciones/{nid}", headers=headers).status_code == 204
    assert client.delete(f"/notificaciones/{nid}", headers=headers).status_code == 404
    assert len(notifs(client, headers)) == 1


def test_no_se_tocan_notificaciones_ajenas(client, headers, headers_otro, con_alertas):
    nid = notifs(client, headers)[0]["id"]
    assert client.patch(f"/notificaciones/{nid}/leer", headers=headers_otro).status_code == 404
    assert client.delete(f"/notificaciones/{nid}", headers=headers_otro).status_code == 404
    client.post("/notificaciones/leer-todas", headers=headers_otro)  # no afecta a los demás
    assert client.get("/notificaciones/conteo", headers=headers).json() == {"no_leidas": 2}
    assert client.get("/notificaciones/conteo", headers=headers_otro).json() == {"no_leidas": 0}
