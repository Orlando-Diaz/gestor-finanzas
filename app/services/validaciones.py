"""Comprobaciones compartidas: las cuentas y categorías referenciadas deben ser del usuario,
no estar archivadas y (en categorías) coincidir con el tipo de movimiento."""

from fastapi import HTTPException
from sqlalchemy import or_, select

from app.models import Categoria, CategoriaOculta, Cuenta, TipoTransaccion


def error_422(mensaje: str) -> HTTPException:
    return HTTPException(422, mensaje)


def cuenta_valida(db, usuario, cuenta_id: int) -> Cuenta:
    cuenta = db.scalar(select(Cuenta).where(Cuenta.id == cuenta_id, Cuenta.usuario_id == usuario.id))
    if cuenta is None:
        raise error_422(f"La cuenta {cuenta_id} no existe")
    if cuenta.archivada:
        raise error_422(f"La cuenta '{cuenta.nombre}' está archivada")
    return cuenta


def categorias_ocultas(db, usuario) -> set[int]:
    """Ids de las predeterminadas que este usuario quitó de su lista."""
    return set(db.scalars(select(CategoriaOculta.categoria_id).where(CategoriaOculta.usuario_id == usuario.id)))


def categoria_valida(db, usuario, categoria_id: int, tipo: TipoTransaccion) -> Categoria:
    categoria = db.scalar(
        select(Categoria).where(
            Categoria.id == categoria_id,
            or_(Categoria.usuario_id.is_(None), Categoria.usuario_id == usuario.id),
        )
    )
    if categoria is None:
        raise error_422(f"La categoría {categoria_id} no existe")
    if categoria.archivada or categoria.id in categorias_ocultas(db, usuario):
        raise error_422(f"La categoría '{categoria.nombre}' está archivada")
    if categoria.tipo.value != tipo.value:
        raise error_422(f"La categoría '{categoria.nombre}' es de {categoria.tipo.value}, no de {tipo.value}")
    return categoria
