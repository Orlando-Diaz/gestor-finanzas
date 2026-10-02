"""La app web (PWA) se sirve desde la misma API."""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "static"


def test_la_raiz_sirve_la_app(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Mis Finanzas" in r.text


def test_el_manifiesto_y_el_service_worker_estan_en_la_raiz(client):
    m = client.get("/manifest.webmanifest")
    assert m.status_code == 200
    datos = m.json()
    assert datos["display"] == "standalone" and datos["start_url"] == "/"
    sw = client.get("/sw.js")
    assert sw.status_code == 200 and "javascript" in sw.headers["content-type"]


def test_los_iconos_del_manifiesto_existen(client):
    for icono in client.get("/manifest.webmanifest").json()["icons"]:
        r = client.get(icono["src"])
        assert r.status_code == 200 and r.headers["content-type"] == "image/png", icono["src"]


def test_todo_lo_que_precarga_el_service_worker_existe(client):
    texto = (RAIZ / "sw.js").read_text(encoding="utf-8")
    rutas = re.findall(r'^\s+"(/[^"]*)",?$', texto, flags=re.M)
    assert len(rutas) > 15
    for ruta in rutas:
        assert client.get(ruta).status_code == 200, f"El service worker precarga {ruta} pero no existe"


def test_cada_modulo_js_importado_existe():
    """Evita el error clásico de un import apuntando a un archivo que no está."""
    for archivo in (RAIZ / "js").rglob("*.js"):
        for ruta in re.findall(r'from "(\.[^"]+)"', archivo.read_text(encoding="utf-8")):
            assert (archivo.parent / ruta).resolve().is_file(), f"{archivo.name} importa {ruta}"


def test_la_api_sigue_teniendo_prioridad_sobre_la_web(client):
    assert client.get("/salud").json() == {"estado": "ok"}
    assert client.get("/docs").status_code == 200
    assert client.get("/cuentas").status_code == 401  # ruta de la API, no un archivo estático
    assert client.get("/no-existe").status_code == 404
