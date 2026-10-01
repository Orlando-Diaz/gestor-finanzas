from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import DbDep, UsuarioActual
from app.models import Categoria, Cuenta, TipoTransaccion, Transaccion
from app.schemas.transaccion import (
    PaginaTransacciones,
    TransaccionActualizar,
    TransaccionCrear,
    TransaccionFiltros,
    TransaccionLeer,
)

router = APIRouter(prefix="/transacciones", tags=["Transacciones"])

# Para devolver nombres de cuenta y categoría sin consultas extra por fila
_CARGAR_RELACIONES = (
    selectinload(Transaccion.cuenta),
    selectinload(Transaccion.cuenta_destino),
    selectinload(Transaccion.categoria),
)


def _error(mensaje: str) -> HTTPException:
    return HTTPException(422, mensaje)


def _cuenta_valida(db, usuario, cuenta_id: int) -> Cuenta:
    cuenta = db.scalar(select(Cuenta).where(Cuenta.id == cuenta_id, Cuenta.usuario_id == usuario.id))
    if cuenta is None:
        raise _error(f"La cuenta {cuenta_id} no existe")
    if cuenta.archivada:
        raise _error(f"La cuenta '{cuenta.nombre}' está archivada")
    return cuenta


def _categoria_valida(db, usuario, categoria_id: int, tipo: TipoTransaccion) -> Categoria:
    categoria = db.scalar(
        select(Categoria).where(
            Categoria.id == categoria_id,
            or_(Categoria.usuario_id.is_(None), Categoria.usuario_id == usuario.id),
        )
    )
    if categoria is None:
        raise _error(f"La categoría {categoria_id} no existe")
    if categoria.archivada:
        raise _error(f"La categoría '{categoria.nombre}' está archivada")
    if categoria.tipo.value != tipo.value:
        raise _error(f"La categoría '{categoria.nombre}' es de {categoria.tipo.value}, no de {tipo.value}")
    return categoria


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
    _cuenta_valida(db, usuario, datos.cuenta_id)
    if datos.tipo == TipoTransaccion.TRANSFERENCIA:
        _cuenta_valida(db, usuario, datos.cuenta_destino_id)
    else:
        _categoria_valida(db, usuario, datos.categoria_id, datos.tipo)

    transaccion = Transaccion(usuario_id=usuario.id, **datos.model_dump())
    db.add(transaccion)
    db.commit()
    return _obtener(db, usuario, transaccion.id)


@router.get("", response_model=PaginaTransacciones)
def listar(filtros: Annotated[TransaccionFiltros, Query()], db: DbDep, usuario: UsuarioActual):
    T = Transaccion
    condiciones = [T.usuario_id == usuario.id]
    if filtros.desde:
        condiciones.append(T.fecha >= filtros.desde)
    if filtros.hasta:
        condiciones.append(T.fecha <= filtros.hasta)
    if filtros.tipo:
        condiciones.append(T.tipo == filtros.tipo)
    if filtros.cuenta_id:
        # una transferencia aparece tanto en la cuenta de origen como en la de destino
        condiciones.append(or_(T.cuenta_id == filtros.cuenta_id, T.cuenta_destino_id == filtros.cuenta_id))
    if filtros.categoria_id:
        # filtrar por una categoría incluye sus subcategorías
        condiciones.append(
            T.categoria_id.in_(
                select(Categoria.id).where(
                    or_(Categoria.id == filtros.categoria_id, Categoria.categoria_padre_id == filtros.categoria_id)
                )
            )
        )

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
            raise _error(f"{campo} no puede ser nulo")

    if es_transferencia:
        if cambios.get("categoria_id") is not None:
            raise _error("Una transferencia no lleva categoría")
        cambios.pop("categoria_id", None)
        if "cuenta_destino_id" in cambios and cambios["cuenta_destino_id"] is None:
            raise _error("Una transferencia necesita cuenta_destino_id")
    else:
        if cambios.get("cuenta_destino_id") is not None:
            raise _error("Solo las transferencias llevan cuenta_destino_id")
        cambios.pop("cuenta_destino_id", None)
        if "categoria_id" in cambios and cambios["categoria_id"] is None:
            raise _error("Un ingreso o gasto necesita categoria_id")

    # Solo se validan las referencias que realmente cambian (una cuenta archivada
    # después no debe impedir corregir la nota de un movimiento viejo).
    if "cuenta_id" in cambios and cambios["cuenta_id"] != transaccion.cuenta_id:
        _cuenta_valida(db, usuario, cambios["cuenta_id"])
    if "cuenta_destino_id" in cambios and cambios["cuenta_destino_id"] != transaccion.cuenta_destino_id:
        _cuenta_valida(db, usuario, cambios["cuenta_destino_id"])
    if "categoria_id" in cambios and cambios["categoria_id"] != transaccion.categoria_id:
        _categoria_valida(db, usuario, cambios["categoria_id"], transaccion.tipo)

    if es_transferencia:
        origen = cambios.get("cuenta_id", transaccion.cuenta_id)
        destino = cambios.get("cuenta_destino_id", transaccion.cuenta_destino_id)
        if origen == destino:
            raise _error("La cuenta de origen y destino deben ser distintas")

    for campo, valor in cambios.items():
        setattr(transaccion, campo, valor)
    db.commit()
    db.expire_all()  # relaciones (cuenta, categoría) pudieron cambiar de id
    return _obtener(db, usuario, transaccion_id)


@router.delete("/{transaccion_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(transaccion_id: int, db: DbDep, usuario: UsuarioActual):
    db.delete(_obtener(db, usuario, transaccion_id))
    db.commit()
