from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import DbDep, UsuarioActual
from app.models import TipoTransaccion, Transaccion
from app.schemas.transaccion import (
    PaginaTransacciones,
    TransaccionActualizar,
    TransaccionCrear,
    TransaccionFiltros,
    TransaccionLeer,
)
from app.services.consultas import condiciones_transacciones
from app.services.presupuestos import evaluar_gasto
from app.services.validaciones import categoria_valida, cuenta_valida, error_422

router = APIRouter(prefix="/transacciones", tags=["Transacciones"])

# Para devolver nombres de cuenta y categoría sin consultas extra por fila
_CARGAR_RELACIONES = (
    selectinload(Transaccion.cuenta),
    selectinload(Transaccion.cuenta_destino),
    selectinload(Transaccion.categoria),
)


def _obtener(db, usuario, transaccion_id: int) -> Transaccion:
    transaccion = db.scalar(
        select(Transaccion)
        .options(*_CARGAR_RELACIONES)
        .where(Transaccion.id == transaccion_id, Transaccion.usuario_id == usuario.id)
    )
    if transaccion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transacción no encontrada")
    return transaccion


@router.post("", response_model=TransaccionLeer, status_code=status.HTTP_201_CREATED)
def crear(datos: TransaccionCrear, db: DbDep, usuario: UsuarioActual):
    cuenta_valida(db, usuario, datos.cuenta_id)
    if datos.tipo == TipoTransaccion.TRANSFERENCIA:
        cuenta_valida(db, usuario, datos.cuenta_destino_id)
    else:
        categoria_valida(db, usuario, datos.categoria_id, datos.tipo)

    transaccion = Transaccion(usuario_id=usuario.id, **datos.model_dump())
    db.add(transaccion)
    db.flush()
    if datos.tipo == TipoTransaccion.GASTO:
        evaluar_gasto(db, usuario.id, datos.categoria_id, datos.fecha)  # alertas de presupuesto
    db.commit()
    return _obtener(db, usuario, transaccion.id)


@router.get("", response_model=PaginaTransacciones)
def listar(filtros: Annotated[TransaccionFiltros, Query()], db: DbDep, usuario: UsuarioActual):
    T = Transaccion
    condiciones = condiciones_transacciones(usuario.id, filtros)
    total = db.scalar(select(func.count()).select_from(T).where(*condiciones))
    items = db.scalars(
        select(T)
        .options(*_CARGAR_RELACIONES)
        .where(*condiciones)
        .order_by(T.fecha.desc(), T.id.desc())
        .limit(filtros.por_pagina)
        .offset((filtros.pagina - 1) * filtros.por_pagina)
    ).all()
    return PaginaTransacciones(items=items, total=total, pagina=filtros.pagina, por_pagina=filtros.por_pagina)


@router.get("/{transaccion_id}", response_model=TransaccionLeer)
def detalle(transaccion_id: int, db: DbDep, usuario: UsuarioActual):
    return _obtener(db, usuario, transaccion_id)


@router.patch("/{transaccion_id}", response_model=TransaccionLeer)
def actualizar(transaccion_id: int, datos: TransaccionActualizar, db: DbDep, usuario: UsuarioActual):
    transaccion = _obtener(db, usuario, transaccion_id)
    cambios = datos.model_dump(exclude_unset=True)
    es_transferencia = transaccion.tipo == TipoTransaccion.TRANSFERENCIA

    for campo in ("monto", "fecha", "cuenta_id"):
        if campo in cambios and cambios[campo] is None:
            raise error_422(f"{campo} no puede ser nulo")

    if es_transferencia:
        if cambios.get("categoria_id") is not None:
            raise error_422("Una transferencia no lleva categoría")
        cambios.pop("categoria_id", None)
        if "cuenta_destino_id" in cambios and cambios["cuenta_destino_id"] is None:
            raise error_422("Una transferencia necesita cuenta_destino_id")
    else:
        if cambios.get("cuenta_destino_id") is not None:
            raise error_422("Solo las transferencias llevan cuenta_destino_id")
        cambios.pop("cuenta_destino_id", None)
        if "categoria_id" in cambios and cambios["categoria_id"] is None:
            raise error_422("Un ingreso o gasto necesita categoria_id")

    # Solo se validan las referencias que realmente cambian (una cuenta archivada
    # después no debe impedir corregir la nota de un movimiento viejo).
    if "cuenta_id" in cambios and cambios["cuenta_id"] != transaccion.cuenta_id:
        cuenta_valida(db, usuario, cambios["cuenta_id"])
    if "cuenta_destino_id" in cambios and cambios["cuenta_destino_id"] != transaccion.cuenta_destino_id:
        cuenta_valida(db, usuario, cambios["cuenta_destino_id"])
    if "categoria_id" in cambios and cambios["categoria_id"] != transaccion.categoria_id:
        categoria_valida(db, usuario, cambios["categoria_id"], transaccion.tipo)

    if es_transferencia:
        origen = cambios.get("cuenta_id", transaccion.cuenta_id)
        destino = cambios.get("cuenta_destino_id", transaccion.cuenta_destino_id)
        if origen == destino:
            raise error_422("La cuenta de origen y destino deben ser distintas")

    for campo, valor in cambios.items():
        setattr(transaccion, campo, valor)
    try:
        db.flush()
        if transaccion.tipo == TipoTransaccion.GASTO:
            evaluar_gasto(db, usuario.id, transaccion.categoria_id, transaccion.fecha)
        db.commit()
    except IntegrityError:  # p. ej. mover un movimiento recurrente a una fecha ya generada
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un movimiento recurrente en esa fecha")
    db.expire_all()  # relaciones (cuenta, categoría) pudieron cambiar de id
    return _obtener(db, usuario, transaccion_id)


@router.delete("/{transaccion_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(transaccion_id: int, db: DbDep, usuario: UsuarioActual):
    db.delete(_obtener(db, usuario, transaccion_id))
    db.commit()
