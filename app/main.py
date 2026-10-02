import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401  (registra todas las tablas en Base.metadata)
from app.api import (
    auth,
    categorias,
    cuentas,
    exportar,
    notificaciones,
    presupuestos,
    recurrentes,
    resumen,
    transacciones,
)
from app.core.database import SessionLocal, engine
from app.core.migraciones import preparar_base_de_datos
from app.services.arranque import tareas_de_arranque

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    preparar_base_de_datos(engine)  # aplica las migraciones pendientes
    with SessionLocal() as db:
        tareas_de_arranque(db)
    yield


app = FastAPI(
    title="Mis Finanzas",
    version="0.4.0",
    description="API de finanzas personales: cuentas, movimientos, presupuestos, recurrentes y resúmenes.",
    lifespan=lifespan,
)
for router in (
    auth.router,
    cuentas.router,
    categorias.router,
    transacciones.router,
    presupuestos.router,
    recurrentes.router,
    notificaciones.router,
    resumen.router,
    exportar.router,
):
    app.include_router(router)


@app.get("/salud", tags=["Salud"])
def salud():
    return {"estado": "ok"}


# La app web (PWA). Va al final para que las rutas de la API tengan prioridad.
DIRECTORIO_WEB = Path(__file__).resolve().parent.parent / "static"
app.mount("/", StaticFiles(directory=DIRECTORIO_WEB, html=True), name="web")
