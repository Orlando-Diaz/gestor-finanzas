from decimal import Decimal

import pytest


def cuenta_id(client, headers, nombre="Efectivo"):
    cuentas = client.get("/cuentas", headers=headers, params={"incluir_archivadas": True}).json()
    return next(c["id"] for c in cuentas if c["nombre"] == nombre)


def nueva_cuenta(client, headers, nombre, saldo="0", tipo="BANCARIA"):
    r = client.post("/cuentas", json={"nombre": nombre, "tipo": tipo, "saldo_inicial": saldo}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def cat_id(client, headers, nombre):
    cats = client.get("/categorias", headers=headers, params={"incluir_archivadas": True}).json()
    return next(c["id"] for c in cats if c["nombre"] == nombre)


def saldo(client, headers, nombre):
    cuentas = client.get("/cuentas", headers=headers).json()
    return Decimal(next(c["saldo_actual"] for c in cuentas if c["nombre"] == nombre))


def gasto(client, headers, monto="18000", fecha="2026-10-01", categoria="Comida", cuenta=None, **extra):
    datos = {
        "tipo": "GASTO",
        "monto": monto,
        "fecha": fecha,
        "cuenta_id": cuenta or cuenta_id(client, headers),
        "categoria_id": cat_id(client, headers, categoria),
        **extra,
    }
    return client.post("/transacciones", json=datos, headers=headers)


def transferencia(client, headers, origen, destino, monto="100000", fecha="2026-10-01"):
    datos = {"tipo": "TRANSFERENCIA", "monto": monto, "fecha": fecha, "cuenta_id": origen, "cuenta_destino_id": destino}
    return client.post("/transacciones", json=datos, headers=headers)


def listar(client, headers, **params):
    r = client.get("/transacciones", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()


# ---------- crear ----------

def test_requiere_autenticacion(client):
    assert client.get("/transacciones").status_code == 401
    assert client.post("/transacciones", json={}).status_code == 401


def test_crear_gasto_descuenta_del_saldo_y_devuelve_nombres(client, headers):
    r = gasto(client, headers, nota="  Almuerzo  ")
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["nota"] == "Almuerzo"
    assert cuerpo["cuenta"]["nombre"] == "Efectivo"
    assert cuerpo["categoria"]["nombre"] == "Comida" and cuerpo["categoria"]["color"]
    assert cuerpo["cuenta_destino"] is None
    assert saldo(client, headers, "Efectivo") == Decimal("-18000")


def test_crear_ingreso_suma(client, headers):
    datos = {"tipo": "INGRESO", "monto": "2500000", "fecha": "2026-10-01",
             "cuenta_id": cuenta_id(client, headers), "categoria_id": cat_id(client, headers, "Salario")}
    assert client.post("/transacciones", json=datos, headers=headers).status_code == 201
    assert saldo(client, headers, "Efectivo") == Decimal("2500000")


def test_transferencia_mueve_plata_sin_contar_como_gasto(client, headers):
    efectivo = cuenta_id(client, headers)
    banco = nueva_cuenta(client, headers, "Bancolombia", "1500000")
    r = transferencia(client, headers, banco, efectivo)
    assert r.status_code == 201
    assert r.json()["cuenta"]["nombre"] == "Bancolombia" and r.json()["cuenta_destino"]["nombre"] == "Efectivo"
    assert saldo(client, headers, "Bancolombia") == Decimal("1400000")
    assert saldo(client, headers, "Efectivo") == Decimal("100000")
    assert listar(client, headers, tipo="GASTO")["total"] == 0


@pytest.mark.parametrize("monto", ["0", "-5", "1.234", "abc"])
def test_monto_invalido(client, headers, monto):
    assert gasto(client, headers, monto=monto).status_code == 422


def test_reglas_de_tipo(client, headers):
    efectivo = cuenta_id(client, headers)
    otra = nueva_cuenta(client, headers, "Nequi")
    comida = cat_id(client, headers, "Comida")
    base = {"monto": "10", "fecha": "2026-10-01", "cuenta_id": efectivo}
    casos = [
        {"tipo": "TRANSFERENCIA", "cuenta_destino_id": efectivo},                      # mismo origen y destino
        {"tipo": "TRANSFERENCIA"},                                                     # sin destino
        {"tipo": "TRANSFERENCIA", "cuenta_destino_id": otra, "categoria_id": comida},  # transferencia con categoría
        {"tipo": "GASTO"},                                                             # sin categoría
        {"tipo": "GASTO", "categoria_id": comida, "cuenta_destino_id": otra},          # gasto con destino
        {"tipo": "OTRO", "categoria_id": comida},
    ]
    for extra in casos:
        assert client.post("/transacciones", json={**base, **extra}, headers=headers).status_code == 422, extra


def test_categoria_debe_coincidir_con_el_tipo(client, headers):
    r = gasto(client, headers, categoria="Salario")  # categoría de INGRESO en un gasto
    assert r.status_code == 422 and "INGRESO" in r.json()["detail"]


def test_no_se_usan_cuentas_ni_categorias_ajenas(client, headers, headers_otro):
    ajena = nueva_cuenta(client, headers_otro, "Ajena")
    assert gasto(client, headers, cuenta=ajena).status_code == 422
    assert transferencia(client, headers, cuenta_id(client, headers), ajena).status_code == 422
    mia = client.post("/categorias", json={"nombre": "Solo mía", "tipo": "GASTO"}, headers=headers_otro).json()
    datos = {"tipo": "GASTO", "monto": "5", "fecha": "2026-10-01",
             "cuenta_id": cuenta_id(client, headers), "categoria_id": mia["id"]}
    assert client.post("/transacciones", json=datos, headers=headers).status_code == 422
    assert gasto(client, headers, cuenta=99999).status_code == 422


def test_no_se_usa_cuenta_ni_categoria_archivada(client, headers):
    vieja = nueva_cuenta(client, headers, "Vieja")
    client.patch(f"/cuentas/{vieja}", json={"archivada": True}, headers=headers)
    assert gasto(client, headers, cuenta=vieja).status_code == 422
    propia = client.post("/categorias", json={"nombre": "Temporal", "tipo": "GASTO"}, headers=headers).json()
    client.patch(f"/categorias/{propia['id']}", json={"archivada": True}, headers=headers)
    assert gasto(client, headers, categoria="Temporal").status_code == 422


# ---------- listar ----------

def test_listado_vacio_y_aislado_por_usuario(client, headers, headers_otro):
    assert listar(client, headers) == {"items": [], "total": 0, "pagina": 1, "por_pagina": 20}
    gasto(client, headers_otro)
    assert listar(client, headers)["total"] == 0


def test_orden_y_paginacion(client, headers):
    for dia in range(1, 8):
        gasto(client, headers, monto=str(dia * 1000), fecha=f"2026-10-0{dia}")
    p1 = listar(client, headers, por_pagina=3, pagina=1)
    p2 = listar(client, headers, por_pagina=3, pagina=2)
    p3 = listar(client, headers, por_pagina=3, pagina=3)
    assert p1["total"] == 7
    fechas = [t["fecha"] for t in p1["items"] + p2["items"] + p3["items"]]
    assert fechas == sorted(fechas, reverse=True) and len(fechas) == 7
    assert len(p3["items"]) == 1
    assert listar(client, headers, por_pagina=3, pagina=9)["items"] == []


def test_filtros_de_fecha_tipo_cuenta_y_categoria(client, headers):
    efectivo = cuenta_id(client, headers)
    banco = nueva_cuenta(client, headers, "Bancolombia", "1000000")
    gasto(client, headers, fecha="2026-09-30", monto="1000")
    gasto(client, headers, fecha="2026-10-05", monto="2000", categoria="Transporte")
    gasto(client, headers, fecha="2026-10-10", monto="3000", cuenta=banco)
    transferencia(client, headers, banco, efectivo, fecha="2026-10-12")

    assert listar(client, headers, desde="2026-10-01")["total"] == 3
    assert listar(client, headers, hasta="2026-09-30")["total"] == 1
    assert listar(client, headers, desde="2026-10-05", hasta="2026-10-10")["total"] == 2
    assert listar(client, headers, tipo="TRANSFERENCIA")["total"] == 1
    # la transferencia aparece en la cuenta de origen Y en la de destino
    assert listar(client, headers, cuenta_id=banco)["total"] == 2
    assert listar(client, headers, cuenta_id=efectivo)["total"] == 3
    assert listar(client, headers, categoria_id=cat_id(client, headers, "Transporte"))["total"] == 1


def test_filtrar_categoria_incluye_subcategorias(client, headers):
    comida = cat_id(client, headers, "Comida")
    hija = client.post("/categorias", json={"nombre": "Domicilios", "tipo": "GASTO",
                                            "categoria_padre_id": comida}, headers=headers).json()
    gasto(client, headers, categoria="Comida")
    gasto(client, headers, categoria="Domicilios")
    gasto(client, headers, categoria="Transporte")
    assert listar(client, headers, categoria_id=comida)["total"] == 2
    assert listar(client, headers, categoria_id=hija["id"])["total"] == 1


@pytest.mark.parametrize("params", [
    {"desde": "2026-10-10", "hasta": "2026-10-01"},
    {"pagina": 0}, {"por_pagina": 0}, {"por_pagina": 101}, {"tipo": "OTRO"}, {"desde": "mañana"},
])
def test_filtros_invalidos(client, headers, params):
    assert client.get("/transacciones", headers=headers, params=params).status_code == 422


# ---------- detalle ----------

def test_detalle_y_aislamiento(client, headers, headers_otro):
    tid = gasto(client, headers_otro).json()["id"]
    assert client.get(f"/transacciones/{tid}", headers=headers).status_code == 404
    assert client.get(f"/transacciones/{tid}", headers=headers_otro).status_code == 200
    assert client.get("/transacciones/99999", headers=headers).status_code == 404


# ---------- editar ----------

def test_editar_monto_actualiza_el_saldo(client, headers):
    tid = gasto(client, headers, monto="18000").json()["id"]
    r = client.patch(f"/transacciones/{tid}", json={"monto": "20000", "nota": "Almuerzo con jugo"}, headers=headers)
    assert r.status_code == 200 and r.json()["nota"] == "Almuerzo con jugo"
    assert saldo(client, headers, "Efectivo") == Decimal("-20000")


def test_editar_cuenta_y_categoria_devuelve_los_nuevos_nombres(client, headers):
    tid = gasto(client, headers).json()["id"]
    nequi = nueva_cuenta(client, headers, "Nequi")
    r = client.patch(f"/transacciones/{tid}",
                     json={"cuenta_id": nequi, "categoria_id": cat_id(client, headers, "Mercado")}, headers=headers)
    assert r.status_code == 200
    assert r.json()["cuenta"]["nombre"] == "Nequi" and r.json()["categoria"]["nombre"] == "Mercado"
    assert saldo(client, headers, "Efectivo") == Decimal("0") and saldo(client, headers, "Nequi") == Decimal("-18000")


def test_borrar_la_nota_con_null(client, headers):
    tid = gasto(client, headers, nota="algo").json()["id"]
    r = client.patch(f"/transacciones/{tid}", json={"nota": None}, headers=headers)
    assert r.status_code == 200 and r.json()["nota"] is None


def test_editar_rechaza_cambios_invalidos(client, headers, headers_otro):
    tid = gasto(client, headers).json()["id"]
    ajena = nueva_cuenta(client, headers_otro, "Ajena")
    invalidos = [
        {"monto": None}, {"fecha": None}, {"cuenta_id": None}, {"categoria_id": None},
        {"monto": "-1"}, {"cuenta_id": ajena}, {"cuenta_id": 99999},
        {"categoria_id": cat_id(client, headers, "Salario")},   # categoría de otro tipo
        {"cuenta_destino_id": ajena},                           # un gasto no lleva destino
        {"tipo": "INGRESO"},                                    # el tipo no se cambia
    ]
    for cuerpo in invalidos:
        assert client.patch(f"/transacciones/{tid}", json=cuerpo, headers=headers).status_code == 422, cuerpo
    assert saldo(client, headers, "Efectivo") == Decimal("-18000")  # nada cambió


def test_editar_transferencia(client, headers):
    efectivo = cuenta_id(client, headers)
    banco = nueva_cuenta(client, headers, "Bancolombia", "1000000")
    nequi = nueva_cuenta(client, headers, "Nequi")
    tid = transferencia(client, headers, banco, efectivo, monto="50000").json()["id"]

    assert client.patch(f"/transacciones/{tid}", json={"categoria_id": cat_id(client, headers, "Comida")},
                        headers=headers).status_code == 422
    assert client.patch(f"/transacciones/{tid}", json={"cuenta_destino_id": banco}, headers=headers).status_code == 422
    assert client.patch(f"/transacciones/{tid}", json={"cuenta_destino_id": None}, headers=headers).status_code == 422
    assert client.patch(f"/transacciones/{tid}", json={"cuenta_destino_id": nequi, "monto": "60000"},
                        headers=headers).status_code == 200
    assert saldo(client, headers, "Bancolombia") == Decimal("940000")
    assert saldo(client, headers, "Nequi") == Decimal("60000")
    assert saldo(client, headers, "Efectivo") == Decimal("0")


def test_editar_nota_de_un_movimiento_en_cuenta_archivada(client, headers):
    vieja = nueva_cuenta(client, headers, "Vieja")
    tid = gasto(client, headers, cuenta=vieja).json()["id"]
    client.patch(f"/cuentas/{vieja}", json={"archivada": True}, headers=headers)
    assert client.patch(f"/transacciones/{tid}", json={"nota": "corregida"}, headers=headers).status_code == 200


def test_no_se_edita_la_transaccion_de_otro(client, headers, headers_otro):
    tid = gasto(client, headers_otro).json()["id"]
    assert client.patch(f"/transacciones/{tid}", json={"nota": "x"}, headers=headers).status_code == 404


# ---------- borrar ----------

def test_borrar_devuelve_el_saldo(client, headers):
    tid = gasto(client, headers).json()["id"]
    assert saldo(client, headers, "Efectivo") == Decimal("-18000")
    assert client.delete(f"/transacciones/{tid}", headers=headers).status_code == 204
    assert saldo(client, headers, "Efectivo") == Decimal("0")
    assert client.get(f"/transacciones/{tid}", headers=headers).status_code == 404


def test_no_se_borra_la_transaccion_de_otro(client, headers, headers_otro):
    tid = gasto(client, headers_otro).json()["id"]
    assert client.delete(f"/transacciones/{tid}", headers=headers).status_code == 404
    assert client.get(f"/transacciones/{tid}", headers=headers_otro).status_code == 200


def test_cuenta_con_movimientos_ya_no_se_puede_borrar(client, headers):
    """Integración con el CRUD de cuentas: protege el historial."""
    cid = cuenta_id(client, headers)
    gasto(client, headers)
    assert client.delete(f"/cuentas/{cid}", headers=headers).status_code == 409
