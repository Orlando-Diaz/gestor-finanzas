from sqlalchemy import or_, select

from app.models import Categoria, Transaccion

T = Transaccion


def condiciones_transacciones(usuario_id: int, filtros) -> list:
    """Condiciones WHERE para filtrar movimientos; las usan el historial y la exportación."""
    condiciones = [T.usuario_id == usuario_id]
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
    return condiciones
