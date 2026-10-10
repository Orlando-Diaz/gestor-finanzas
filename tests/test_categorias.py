from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import Categoria, Cuenta, Presupuesto, TipoTransaccion, Transaccion


def crear(client, headers, **datos):
    base = {"nombre": "Gimnasio", "tipo": "GASTO", "color": "#112233", "icono": "🏋️"}
    return client.post("/categorias", json={**base, **datos}, headers=headers)


def listar(client, headers, **params):
    return client.get("/categorias", headers=headers, params=params).json()


def predeterminada(db, nombre):
    return db.scalar(select(Categoria).where(Categoria.nombre == nombre, Categoria.usuario_id.is_(None)))


def test_requiere_autenticacion(client):
    assert client.get("/categorias").status_code == 401


def test_listado_trae_predeterminadas_y_filtra_por_tipo(client, headers):
    todas = listar(client, headers)
    assert len(todas) == 18 and all(c["predeterminada"] for c in todas)
    assert {c["tipo"] for c in listar(client, headers, tipo="INGRESO")} == {"INGRESO"}
    assert len(listar(client, headers, tipo="INGRESO")) == 6


def test_crear_categoria_propia_solo_la_ve_su_dueño(client, headers, headers_otro):
    r = crear(client, headers)
    assert r.status_code == 201 and r.json()["predeterminada"] is False
    assert any(c["nombre"] == "Gimnasio" for c in listar(client, headers))
    assert all(c["nombre"] != "Gimnasio" for c in listar(client, headers_otro))


def test_nombre_repetido_con_predeterminada_o_propia(client, headers):
    assert crear(client, headers, nombre="comida").status_code == 409  # existe predeterminada Comida
    assert crear(client, headers).status_code == 201
    assert crear(client, headers, nombre=" GIMNASIO ").status_code == 409
    # mismo nombre pero de otro tipo sí se permite
    assert crear(client, headers, nombre="Gimnasio", tipo="INGRESO").status_code == 201


def test_datos_invalidos(client, headers):
    assert crear(client, headers, color="rojo").status_code == 422
    assert crear(client, headers, nombre="  ").status_code == 422
    assert crear(client, headers, tipo="OTRO").status_code == 422


def test_subcategorias(client, headers, db):
    comida = predeterminada(db, "Comida")
    ok = crear(client, headers, nombre="Domicilios", categoria_padre_id=comida.id)
    assert ok.status_code == 201 and ok.json()["categoria_padre_id"] == comida.id
    # tipo distinto al del padre
    assert crear(client, headers, nombre="X", tipo="INGRESO", categoria_padre_id=comida.id).status_code == 422
    # solo un nivel
    assert crear(client, headers, nombre="Y", categoria_padre_id=ok.json()["id"]).status_code == 422
    # padre inexistente
    assert crear(client, headers, nombre="Z", categoria_padre_id=99999).status_code == 404


def test_no_se_puede_usar_como_padre_la_categoria_de_otro(client, headers, headers_otro):
    ajena = crear(client, headers_otro, nombre="Ajena").json()
    assert crear(client, headers, nombre="Hija", categoria_padre_id=ajena["id"]).status_code == 404


def test_predeterminadas_no_se_pueden_editar(client, headers, db):
    p = predeterminada(db, "Salario")
    assert client.patch(f"/categorias/{p.id}", json={"nombre": "Mi sueldo"}, headers=headers).status_code == 403
    assert client.patch(f"/categorias/{p.id}", json={"archivada": True}, headers=headers).status_code == 403


def test_quitar_predeterminada_solo_afecta_a_quien_la_quita(client, headers, headers_otro, db):
    p = predeterminada(db, "Mascotas")
    assert client.delete(f"/categorias/{p.id}", headers=headers).status_code == 204
    assert all(c["id"] != p.id for c in listar(client, headers))
    assert any(c["id"] == p.id for c in listar(client, headers_otro))
    # con incluir_archivadas sale marcada como archivada, para poder restaurarla
    quitada = next(c for c in listar(client, headers, incluir_archivadas=True) if c["id"] == p.id)
    assert quitada["archivada"] is True and quitada["predeterminada"] is True
    # quitarla otra vez no falla, y la fila compartida sigue existiendo
    assert client.delete(f"/categorias/{p.id}", headers=headers).status_code == 204
    assert predeterminada(db, "Mascotas") is not None


def test_se_pueden_quitar_todas_las_predeterminadas_aunque_tengan_historial(client, headers, db):
    uid = client.get("/auth/me", headers=headers).json()["id"]
    cuenta = db.scalar(select(Cuenta).where(Cuenta.usuario_id == uid))
    comida = predeterminada(db, "Comida")
    db.add(Transaccion(usuario_id=uid, cuenta_id=cuenta.id, categoria_id=comida.id,
                       tipo=TipoTransaccion.GASTO, monto=Decimal("5"), fecha=date(2026, 10, 1)))
    db.commit()
    for c in listar(client, headers):
        assert client.delete(f"/categorias/{c['id']}", headers=headers).status_code == 204
    assert listar(client, headers) == []
    # el historial conserva su categoría
    movs = client.get("/transacciones", headers=headers).json()["items"]
    assert movs[0]["categoria"]["nombre"] == "Comida"


def test_categoria_quitada_no_se_puede_usar_en_movimientos_nuevos(client, headers, db):
    p = predeterminada(db, "Mascotas")
    cuenta = client.get("/cuentas", headers=headers).json()[0]
    mov = {"tipo": "GASTO", "cuenta_id": cuenta["id"], "categoria_id": p.id, "monto": "10", "fecha": "2026-10-01"}
    assert client.post("/transacciones", json=mov, headers=headers).status_code == 201
    client.delete(f"/categorias/{p.id}", headers=headers)
    assert client.post("/transacciones", json=mov, headers=headers).status_code == 422


def test_nombre_de_predeterminada_quitada_queda_libre(client, headers):
    comida = next(c for c in listar(client, headers) if c["nombre"] == "Comida")
    assert crear(client, headers, nombre="Comida").status_code == 409
    client.delete(f"/categorias/{comida['id']}", headers=headers)
    assert crear(client, headers, nombre="Comida").status_code == 201


def test_restaurar_predeterminadas(client, headers):
    todas = listar(client, headers)
    for c in todas[:3]:
        client.delete(f"/categorias/{c['id']}", headers=headers)
    assert len(listar(client, headers)) == len(todas) - 3
    r = client.post("/categorias/restaurar-predeterminadas", headers=headers)
    assert r.status_code == 200 and r.json() == {"restauradas": 3}
    assert len(listar(client, headers)) == len(todas)
    assert client.post("/categorias/restaurar-predeterminadas", headers=headers).json() == {"restauradas": 0}


def test_restaurar_no_duplica_si_ya_creaste_una_igual(client, headers):
    comida = next(c for c in listar(client, headers) if c["nombre"] == "Comida")
    client.delete(f"/categorias/{comida['id']}", headers=headers)
    crear(client, headers, nombre="Comida")
    assert client.post("/categorias/restaurar-predeterminadas", headers=headers).json() == {"restauradas": 0}
    assert [c["nombre"] for c in listar(client, headers)].count("Comida") == 1


def test_restaurar_requiere_autenticacion(client):
    assert client.post("/categorias/restaurar-predeterminadas").status_code == 401


def test_no_se_toca_la_categoria_de_otro_usuario(client, headers, headers_otro):
    ajena = crear(client, headers_otro, nombre="Ajena").json()
    assert client.patch(f"/categorias/{ajena['id']}", json={"nombre": "x"}, headers=headers).status_code == 404
    assert client.delete(f"/categorias/{ajena['id']}", headers=headers).status_code == 404


def test_actualizar_y_archivar(client, headers):
    c = crear(client, headers).json()
    r = client.patch(f"/categorias/{c['id']}", json={"nombre": "Deporte", "color": "#ABCDEF"}, headers=headers)
    assert r.status_code == 200 and r.json()["nombre"] == "Deporte"
    assert client.patch(f"/categorias/{c['id']}", json={"nombre": None}, headers=headers).status_code == 422
    assert client.patch(f"/categorias/{c['id']}", json={"nombre": "Comida"}, headers=headers).status_code == 409
    client.patch(f"/categorias/{c['id']}", json={"archivada": True}, headers=headers)
    assert all(x["id"] != c["id"] for x in listar(client, headers))
    assert any(x["id"] == c["id"] for x in listar(client, headers, incluir_archivadas=True))


def test_borrar_categoria_sin_uso(client, headers):
    c = crear(client, headers).json()
    assert client.delete(f"/categorias/{c['id']}", headers=headers).status_code == 204
    assert all(x["id"] != c["id"] for x in listar(client, headers))


def test_no_se_borra_categoria_en_uso(client, headers, db):
    uid = client.get("/auth/me", headers=headers).json()["id"]
    cuenta = db.scalar(select(Cuenta).where(Cuenta.usuario_id == uid))

    con_gasto = crear(client, headers, nombre="ConGasto").json()
    db.add(Transaccion(usuario_id=uid, cuenta_id=cuenta.id, categoria_id=con_gasto["id"],
                       tipo=TipoTransaccion.GASTO, monto=Decimal("1"), fecha=date(2026, 10, 1)))
    con_presupuesto = crear(client, headers, nombre="ConPresupuesto").json()
    db.add(Presupuesto(usuario_id=uid, categoria_id=con_presupuesto["id"], monto_limite=Decimal("100"),
                       mes=10, anio=2026))
    padre = crear(client, headers, nombre="Padre").json()
    crear(client, headers, nombre="Hija", categoria_padre_id=padre["id"])
    db.commit()

    for c in (con_gasto, con_presupuesto, padre):
        assert client.delete(f"/categorias/{c['id']}", headers=headers).status_code == 409
