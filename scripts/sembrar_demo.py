"""Crea un usuario de demostración con datos de ejemplo (6 meses de movimientos, presupuestos, metas y deudas).

Usa la API pública, así que sirve contra tu servidor local o contra el desplegado:

    python scripts/sembrar_demo.py                                   # http://127.0.0.1:8000
    python scripts/sembrar_demo.py https://mis-finanzas-xxxx.onrender.com

Si el usuario ya existe, solo inicia sesión y NO vuelve a sembrar (no duplica datos).
"""
import json
import random
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
EMAIL, CLAVE, NOMBRE = "demo@misfinanzas.app", "demo-1234-clave", "Camila Demo"
hoy = (datetime.now(timezone.utc) - timedelta(hours=5)).date()


def llamar(metodo, ruta, cuerpo=None, token=None, formulario=False):
    datos = None
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if cuerpo is not None:
        if formulario:
            from urllib.parse import urlencode
            datos = urlencode(cuerpo).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            datos = json.dumps(cuerpo).encode()
            headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + ruta, data=datos, method=metodo, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, json.loads(r.read() or "null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or "null")


def mes_atras(n):
    total = hoy.year * 12 + hoy.month - 1 - n
    return total // 12, total % 12 + 1


def main():
    estado, _ = llamar("POST", "/auth/registro", {"nombre": NOMBRE, "email": EMAIL, "password": CLAVE})
    if estado == 409 or estado == 400:
        print("El usuario demo ya existe: no se siembra de nuevo.")
        sys.exit(0)
    assert estado == 201, estado
    _, tok = llamar("POST", "/auth/login", {"username": EMAIL, "password": CLAVE}, formulario=True)
    t = tok["access_token"]
    ok = lambda m, r, c=None: llamar(m, r, c, t)[1]  # noqa: E731

    cats = {c["nombre"]: c["id"] for c in ok("GET", "/categorias")}
    efectivo = next(c["id"] for c in ok("GET", "/cuentas") if c["nombre"] == "Efectivo")
    ok("PATCH", f"/cuentas/{efectivo}", {"saldo_inicial": "1500000"})
    banco = ok("POST", "/cuentas", {"nombre": "Bancolombia", "tipo": "BANCARIA", "saldo_inicial": "1800000"})["id"]
    nequi = ok("POST", "/cuentas", {"nombre": "Nequi", "tipo": "BILLETERA_DIGITAL", "saldo_inicial": "150000"})["id"]

    azar = random.Random(7)
    mov = lambda tipo, monto, f, cuenta, cat, nota=None: ok("POST", "/transacciones", {  # noqa: E731
        "tipo": tipo, "monto": str(monto), "fecha": f.isoformat(), "cuenta_id": cuenta, "categoria_id": cats[cat], "nota": nota})

    for n in range(5, -1, -1):
        anio, mes = mes_atras(n)
        ultimo = hoy.day if n == 0 else 28
        d = lambda dia: date(anio, mes, min(dia, ultimo))  # noqa: E731
        if d(1) > hoy:
            continue
        mov("INGRESO", 3200000, d(1), banco, "Salario", "Salario del mes")
        if n % 2 == 0 and d(18) <= hoy:
            mov("INGRESO", azar.choice([350000, 480000, 600000]), d(18), nequi, "Freelance", "Proyecto web")
        mov("GASTO", 850000, d(2), banco, "Arriendo", "Arriendo")
        if d(5) <= hoy:
            mov("GASTO", azar.randint(110, 160) * 1000, d(5), banco, "Servicios públicos", "Luz, agua e internet")
        if d(6) <= hoy:
            mov("GASTO", 38900, d(6), banco, "Suscripciones", "Streaming")
        for dia in range(3, 28, 3):
            if d(dia) > hoy:
                break
            mov("GASTO", azar.randint(14, 48) * 1000, d(dia), azar.choice([nequi, efectivo]), "Comida", azar.choice(["Almuerzo", "Domicilio", "Cena", "Café"]))
            if dia % 2 == 0:
                mov("GASTO", azar.randint(90, 220) * 1000, d(dia), banco, "Mercado", "Mercado de la semana")
            if dia % 4 == 0:
                mov("GASTO", azar.randint(6, 25) * 1000, d(dia), efectivo, "Transporte", "Bus / taxi")
        if d(14) <= hoy:
            mov("GASTO", azar.randint(40, 120) * 1000, d(14), nequi, "Entretenimiento", "Cine y salida")
        if n % 2 == 1 and d(20) <= hoy:
            mov("GASTO", azar.randint(80, 190) * 1000, d(20), banco, "Ropa", "Compras")
        if d(9) <= hoy:
            ok("POST", "/transacciones", {"tipo": "TRANSFERENCIA", "monto": "200000", "fecha": d(9).isoformat(), "cuenta_id": banco, "cuenta_destino_id": nequi, "nota": "Recarga Nequi"})

    for anio, mes in (mes_atras(1), mes_atras(0)):
        for cat, limite in [("Comida", 450000), ("Mercado", 600000), ("Transporte", 120000), ("Entretenimiento", 150000)]:
            ok("POST", "/presupuestos", {"categoria_id": cats[cat], "monto_limite": str(limite), "mes": mes, "anio": anio})
    ok("POST", "/recurrentes", {"tipo": "GASTO", "monto": "850000", "cuenta_id": banco, "categoria_id": cats["Arriendo"],
                                "frecuencia": "MENSUAL", "proxima_fecha": date(*mes_atras(-1), 2).isoformat(), "nota": "Arriendo"})

    m = ok("POST", "/metas", {"nombre": "Viaje a Cartagena", "monto_objetivo": "2000000", "icono": "✈️", "color": "#0e7490",
                              "fecha_objetivo": (hoy + timedelta(days=150)).isoformat()})
    ok("POST", f"/metas/{m['id']}/aportes", {"tipo": "APORTE", "monto": "700000"})
    ok("POST", f"/metas/{m['id']}/aportes", {"tipo": "APORTE", "monto": "350000"})
    m = ok("POST", "/metas", {"nombre": "Fondo de emergencia", "monto_objetivo": "5000000", "icono": "🛟", "color": "#b45309"})
    ok("POST", f"/metas/{m['id']}/aportes", {"tipo": "APORTE", "monto": "1200000"})

    d1 = ok("POST", "/deudas", {"tipo": "ME_DEBEN", "persona": "Carlos", "descripcion": "Préstamo para el arriendo", "monto_total": "300000",
                                "fecha": (hoy - timedelta(days=40)).isoformat(), "fecha_vencimiento": (hoy - timedelta(days=5)).isoformat()})
    ok("POST", f"/deudas/{d1['id']}/pagos", {"monto": "100000"})
    ok("POST", "/deudas", {"tipo": "ME_DEBEN", "persona": "Laura", "descripcion": "Entradas al concierto", "monto_total": "180000"})
    d3 = ok("POST", "/deudas", {"tipo": "DEBO", "persona": "Mamá", "descripcion": "Préstamo del computador", "monto_total": "1200000",
                                "fecha_vencimiento": (hoy + timedelta(days=60)).isoformat()})
    ok("POST", f"/deudas/{d3['id']}/pagos", {"monto": "400000"})
    print(f"Listo. Entra con {EMAIL} / {CLAVE}")


main()
