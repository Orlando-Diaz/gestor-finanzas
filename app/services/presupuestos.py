from datetime import date
from decimal import Decimal

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.tiempo import rango_mes
from app.models import Categoria, Notificacion, Presupuesto, TipoNotificacion, TipoTransaccion, Transaccion
from app.services.saldos import CENTAVOS

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def cop(valor: Decimal) -> str:
    """1234567 -> $1.234.567"""
    return "$" + format(Decimal(valor), ",.0f").replace(",", ".")


def gastado_en_periodo(db: Session, usuario_id: int, categoria_id: int, anio: int, mes: int) -> Decimal:
    """Gasto del mes en la categoría y en sus subcategorías."""
    inicio, fin = rango_mes(anio, mes)
    total = db.scalar(
        select(func.coalesce(func.sum(Transaccion.monto), 0)).where(
            Transaccion.usuario_id == usuario_id,
            Transaccion.tipo == TipoTransaccion.GASTO,
            Transaccion.fecha >= inicio,
            Transaccion.fecha < fin,
            Transaccion.categoria_id.in_(
                select(Categoria.id).where(
                    or_(Categoria.id == categoria_id, Categoria.categoria_padre_id == categoria_id)
                )
            ),
        )
    )
    return Decimal(str(total)).quantize(CENTAVOS)


def calcular_progreso(presupuesto: Presupuesto, gastado: Decimal) -> dict:
    limite = Decimal(presupuesto.monto_limite)
    if gastado > limite:
        estado = "EXCEDIDO"
    elif gastado * 100 >= presupuesto.umbral_alerta * limite:  # comparación exacta, sin redondeos
        estado = "ALERTA"
    else:
        estado = "OK"
    return {
        "gastado": gastado,
        "restante": (limite - gastado).quantize(CENTAVOS),
        "porcentaje": (gastado * 100 / limite).quantize(CENTAVOS),
        "estado": estado,
    }


def evaluar_presupuesto(db: Session, presupuesto: Presupuesto) -> None:
    """Crea la notificación de alerta o de exceso si corresponde (una sola vez por presupuesto)."""
    gastado = gastado_en_periodo(db, presupuesto.usuario_id, presupuesto.categoria_id, presupuesto.anio, presupuesto.mes)
    progreso = calcular_progreso(presupuesto, gastado)
    if progreso["estado"] == "OK":
        return

    tipo = TipoNotificacion.PRESUPUESTO_EXCEDIDO if progreso["estado"] == "EXCEDIDO" else TipoNotificacion.PRESUPUESTO_UMBRAL
    ya_avisado = db.scalar(
        select(Notificacion.id)
        .where(
            Notificacion.presupuesto_id == presupuesto.id,
            Notificacion.tipo.in_([tipo, TipoNotificacion.PRESUPUESTO_EXCEDIDO]),
        )
        .limit(1)
    )
    if ya_avisado:  # si ya avisamos que se excedió, no tiene sentido avisar después del umbral
        return

    categoria = db.get(Categoria, presupuesto.categoria_id)
    periodo = f"{MESES[presupuesto.mes - 1]} {presupuesto.anio}"
    if tipo == TipoNotificacion.PRESUPUESTO_EXCEDIDO:
        mensaje = f"Superaste el presupuesto de {categoria.nombre} ({periodo}): {cop(gastado)} de {cop(presupuesto.monto_limite)}"
    else:
        mensaje = (
            f"Vas en {progreso['porcentaje']:.0f}% del presupuesto de {categoria.nombre} ({periodo}): "
            f"{cop(gastado)} de {cop(presupuesto.monto_limite)}"
        )
    db.add(Notificacion(usuario_id=presupuesto.usuario_id, tipo=tipo, mensaje=mensaje, presupuesto_id=presupuesto.id))


def evaluar_gasto(db: Session, usuario_id: int, categoria_id: int, fecha: date) -> None:
    """Llamar tras registrar o cambiar un gasto (con los cambios ya enviados a la BD con flush).

    Revisa el presupuesto de la categoría y el de su categoría padre, porque este cuenta lo de sus subcategorías.
    """
    categoria = db.get(Categoria, categoria_id)
    ids = {categoria_id}
    if categoria is not None and categoria.categoria_padre_id:
        ids.add(categoria.categoria_padre_id)
    presupuestos = db.scalars(
        select(Presupuesto).where(
            Presupuesto.usuario_id == usuario_id,
            Presupuesto.anio == fecha.year,
            Presupuesto.mes == fecha.month,
            Presupuesto.categoria_id.in_(ids),
        )
    ).all()
    for p in presupuestos:
        evaluar_presupuesto(db, p)


def reiniciar_alertas(db: Session, presupuesto_id: int) -> None:
    """Al cambiar el límite se borran sus alertas, para que puedan volver a dispararse."""
    db.execute(
        delete(Notificacion).where(
            Notificacion.presupuesto_id == presupuesto_id,
            Notificacion.tipo.in_([TipoNotificacion.PRESUPUESTO_UMBRAL, TipoNotificacion.PRESUPUESTO_EXCEDIDO]),
        )
    )
