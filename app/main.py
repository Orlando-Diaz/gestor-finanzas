from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.models  # noqa: F401  (registra todas las tablas en Base.metadata)
from app.api import auth, categorias, cuentas, transacciones
from app.core.database import Base, SessionLocal, engine
from app.services.categorias_default import sembrar_categorias_default


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Por ahora create_all; más adelante lo reemplazamos por migraciones con Alembic
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        sembrar_categorias_default(db)
    yield


app = FastAPI(title="Mis Finanzas", version="0.2.0", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(cuentas.router)
app.include_router(categorias.router)
app.include_router(transacciones.router)


@app.get("/salud")
def salud():
    return {"estado": "ok"}
