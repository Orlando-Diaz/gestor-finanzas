import csv
import io
from datetime import date

import pytest

import app.api.exportar as modulo_exportar
from app.core import tiempo


def cuenta_id(client, headers, nombre="Efectivo"):
    return next(c["id"] for c in client.get("/cuentas", headers=headers).json() if c["nombre"] == nombre)


def cat_id(client, headers, nombre):
    return next(c["id"] for c in client.get("/categorias", headers=headers).json() if c["nombre"] == nombre)


def mov(client, headers, tipo="GASTO", monto="18000", fecha="2026-10-01", categoria="Comida", nota=None, cuenta=None):
    r = client.post("/transacciones", headers=headers, json={
        "tipo": tipo, "monto": monto, "fecha": fecha, "cuenta_id": cuenta or cuenta_id(client, headers),
        "categoria_id": cat_id(client, headers, categoria), "nota": nota})
    assert r.status_code == 201, r.text


def descargar(client, headers, **params):
    r = client.get("/exportar/transacciones", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r


def filas(respuesta, delimiter=";"):
    texto = respuesta.content.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(texto, newline=""), delimiter=delimiter))


ENCABEZADO = ["Fecha", "Tipo", "Monto", "Cuenta", "Cuenta destino", "Categoría", "Nota"]


def test_requiere_autenticacion(client):
    assert client.get("/exportar/transacciones").status_code == 401


def test_formato_por_defecto_para_excel_en_colombia(client, headers, monkeypatch):
    monkeypatch.setattr(tiempo, "hoy", lambda: date(2026, 10, 20))
    mov(client, headers, nota="Almuerzo", monto="18000.5")
    r = descargar(client, headers)
    assert r.headers["content-type"].startswith("text/csv")
    assert r.headers["content-disposition"] == 'attachment; filename="transacciones_2026-10-20.csv"'
    assert r.content.startswith(b"\xef\xbb\xbf")  # BOM UTF-8
    assert b"\r\n" in r.content
    assert filas(r) == [ENCABEZADO, ["2026-10-01", "Gasto", "18000,50", "Efectivo", "", "Comida", "Almuerzo"]]


def test_formato_estandar_con_coma_y_punto(client, headers):
    mov(client, headers, monto="18000.5")
    r = descargar(client, headers, separador=",", decimal=".")
    assert filas(r, ",")[1][2] == "18000.50"


def test_sin_movimientos_solo_trae_el_encabezado(client, headers):
    assert filas(descargar(client, headers)) == [ENCABEZADO]


def test_tipos_transferencia_y_orden_cronologico(client, headers):
    efectivo = cuenta_id(client, headers)
    banco = client.post("/cuentas", headers=headers, json={"nombre": "Banco", "tipo": "BANCARIA", "saldo_inicial": "0"}).json()["id"]
    mov(client, headers, fecha="2026-10-09")
    mov(client, headers, "INGRESO", "100", fecha="2026-10-02", categoria="Salario")
    client.post("/transacciones", headers=headers, json={
        "tipo": "TRANSFERENCIA", "monto": "5000", "fecha": "2026-10-05", "cuenta_id": banco, "cuenta_destino_id": efectivo})
    datos = filas(descargar(client, headers))[1:]
    assert [f[0] for f in datos] == ["2026-10-02", "2026-10-05", "2026-10-09"]  # del más antiguo al más reciente
    assert [f[1] for f in datos] == ["Ingreso", "Transferencia", "Gasto"]
    assert datos[1][3:6] == ["Banco", "Efectivo", ""]  # origen, destino y sin categoría


def test_respeta_los_filtros_del_historial(client, headers):
    mov(client, headers, fecha="2026-09-30")
    mov(client, headers, fecha="2026-10-15", categoria="Transporte")
    mov(client, headers, "INGRESO", "1", fecha="2026-10-16", categoria="Salario")
    assert len(filas(descargar(client, headers))) == 4
    assert len(filas(descargar(client, headers, desde="2026-10-01"))) == 3
    assert len(filas(descargar(client, headers, desde="2026-10-01", hasta="2026-10-15"))) == 2
    assert len(filas(descargar(client, headers, tipo="INGRESO"))) == 2
    assert filas(descargar(client, headers, categoria_id=cat_id(client, headers, "Transporte")))[1][5] == "Transporte"


def test_protege_contra_inyeccion_de_formulas(client, headers):
    for nota in ("=SUMA(A1:A9)", "+1+1", "-2", "@cmd", "normal=ok"):
        mov(client, headers, nota=nota)
    notas = [f[6] for f in filas(descargar(client, headers))[1:]]
    assert notas == ["'=SUMA(A1:A9)", "'+1+1", "'-2", "'@cmd", "normal=ok"]


def test_notas_con_separador_comillas_y_saltos_de_linea_se_conservan(client, headers):
    nota = 'Pan; leche, "huevos"\ny queso'
    mov(client, headers, nota=nota)
    assert filas(descargar(client, headers))[1][6] == nota
    assert filas(descargar(client, headers, separador=","), ",")[1][6] == nota


def test_tildes_y_enes_en_utf8(client, headers):
    client.post("/categorias", headers=headers, json={"nombre": "Niño & café", "tipo": "GASTO"})
    mov(client, headers, categoria="Niño & café", nota="Ñandú")
    fila = filas(descargar(client, headers))[1]
    assert fila[5] == "Niño & café" and fila[6] == "Ñandú"


def test_solo_exporta_los_datos_del_usuario(client, headers, headers_otro):
    mov(client, headers_otro, nota="secreto")
    assert filas(descargar(client, headers)) == [ENCABEZADO]


@pytest.mark.parametrize("params", [{"separador": "|"}, {"decimal": "x"}, {"desde": "2026-10-10", "hasta": "2026-10-01"}, {"tipo": "OTRO"}])
def test_parametros_invalidos(client, headers, params):
    assert client.get("/exportar/transacciones", headers=headers, params=params).status_code == 422


def test_rechaza_exportaciones_enormes(client, headers, monkeypatch):
    monkeypatch.setattr(modulo_exportar, "MAX_FILAS", 2)
    for dia in (1, 2, 3):
        mov(client, headers, fecha=f"2026-10-0{dia}")
    assert client.get("/exportar/transacciones", headers=headers).status_code == 422
    assert client.get("/exportar/transacciones", headers=headers, params={"desde": "2026-10-02"}).status_code == 200
