import logging
from calendar import monthrange
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import tiempo
from app.models import (
    Categoria,
    Frecuencia,
    Notificacion,
    TipoNotificacion,
    TipoTransaccion,
    Transaccion,
    TransaccionRecurrente,
)
from app.services.presupuestos import cop, evaluar_gasto

log = logging.getLogger(__name__)

MAX_POR_EJECUCION = 400  # tope de movimientos por recurrente en una pasada (evita bucles enormes)


def ultimo_dia_del_mes(d: date) -> int:
    return monthrange(d.year, d.month)[1]


def fecha_quincenal_valida(d: date) -> bool:
    """La frecuencia QUINCENAL es 'el 15 y el último día de cada mes' (como se paga la nómina)."""
    return d.day == 15 or d.day == ultimo_dia_del_mes(d)


def _con_dia_ajustado(anio: int, mes: int, dia: int) -> date:
    return date(anio, mes, min(dia, monthrange(anio, mes)[1]))


def siguiente_fecha(frecuencia: Frecuencia, actual: date, dia_ancla: int) -> date:
    if frecuencia == Frecuencia.SEMANAL:
        return actual + timedelta(days=7)
    if frecuencia == Frecuencia.QUINCENAL:
        if actual.day == 15:
            return actual.replace(day=ultimo_dia_del_mes(actual))
        anio, mes = tiempo.sumar_meses(actual.year, actual.month, 1)
        return date(anio, mes, 15)
    if frecuencia == Frecuencia.MENSUAL:
        anio, mes = tiempo.sumar_meses(actual.year, actual.month, 1)
        return _con_dia_ajustado(anio, mes, dia_ancla)
    if frecuencia == Frecuencia.ANUAL:
        return _con_dia_ajustado(actual.year + 1, actual.month, dia_ancla)
    raise ValueError(f"Frecuencia desconocida: {frecuencia}")


def _procesar_una(db: Session, recurrente_id: int, hasta: date) -> int:
    r = db.get(TransaccionRecurrente, recurrente_id)
    if r is None or not r.activa:
        return 0

    generadas = 0
    gastos_a_evaluar: set[tuple[int, date]] = set()
    while r.activa and r.proxima_fecha <= hasta and generadas < MAX_POR_EJECUCION:
        if r.fecha_fin and r.proxima_fecha > r.fecha_fin:
            r.activa = False
            break
        ya_existe = db.scalar(
            select(Transaccion.id).where(Transaccion.recurrente_id == r.id, Transaccion.fecha == r.proxima_fecha)
        )
        if not ya_existe:  # si ya está registrado ese día, solo se avanza la fecha
            db.add(
                Transaccion(
                    usuario_id=r.usuario_id, cuenta_id=r.cuenta_id, categoria_id=r.categoria_id,
                    recurrente_id=r.id, tipo=r.tipo, monto=r.monto, fecha=r.proxima_fecha, nota=r.nota,
                )
            )
            generadas += 1
            if r.tipo == TipoTransaccion.GASTO:
                gastos_a_evaluar.add((r.categoria_id, r.proxima_fecha))
        r.proxima_fecha = siguiente_fecha(r.frecuencia, r.proxima_fecha, r.dia_ancla)
    if r.fecha_fin and r.proxima_fecha > r.fecha_fin:
        r.activa = False  # ya cumplió todas sus repeticiones

    try:
        db.flush()
        for categoria_id, fecha in gastos_a_evaluar:
            evaluar_gasto(db, r.usuario_id, categoria_id, fecha)
        if generadas:
            categoria = db.get(Categoria, r.categoria_id)
            descripcion = r.nota or categoria.nombre
            mensaje = (
                f"Se registró {descripcion}: {cop(r.monto)}"
                if generadas == 1
                else f"Se registraron {generadas} movimientos de {descripcion} ({cop(r.monto)} c/u)"
            )
            db.add(Notificacion(usuario_id=r.usuario_id, tipo=TipoNotificacion.RECURRENTE_REGISTRADA, mensaje=mensaje[:255]))
        db.commit()
    except IntegrityError:
        # otro proceso generó lo mismo a la vez: se descarta esta pasada y la siguiente ya lo encuentra hecho
        db.rollback()
        log.warning("Conflicto al procesar la recurrente %s; se reintentará", recurrente_id)
        return 0
    return generadas


def procesar_recurrentes(db: Session, usuario_id: int | None = None, hasta: date | None = None) -> int:
    """Registra los ingresos/gastos recurrentes que ya vencieron. Devuelve cuántos movimientos creó.

    Es idempotente: se puede llamar cuantas veces se quiera. Con `usuario_id=None` procesa a todos.
    """
    hasta = hasta or tiempo.hoy()
    consulta = select(TransaccionRecurrente.id).where(
        TransaccionRecurrente.activa.is_(True), TransaccionRecurrente.proxima_fecha <= hasta
    )
    if usuario_id is not None:
        consulta = consulta.where(TransaccionRecurrente.usuario_id == usuario_id)
    return sum(_procesar_una(db, rid, hasta) for rid in db.scalars(consulta).all())
