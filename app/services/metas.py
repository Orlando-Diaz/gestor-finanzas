from datetime import date
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core import tiempo
from app.models import AporteMeta, Meta, Notificacion, TipoAporte, TipoNotificacion
from app.schemas.meta import AporteLeer, MetaDetalle, MetaLeer
from app.services.presupuestos import cop
from app.services.saldos import CENTAVOS

CERO = Decimal("0.00")


def ahorrado(db: Session, meta_id: int) -> Decimal:
    """Aportes menos retiros."""
    total = db.scalar(
        select(func.coalesce(func.sum(case((AporteMeta.tipo == TipoAporte.APORTE, AporteMeta.monto), else_=-AporteMeta.monto)), 0))
        .where(AporteMeta.meta_id == meta_id)
    )
    return Decimal(str(total)).quantize(CENTAVOS)


def meses_restantes(hasta: date, hoy: date) -> int:
    """Meses de calendario que quedan hasta la fecha (mínimo 1 si la fecha aún no llega)."""
    return max(1, (hasta.year * 12 + hasta.month) - (hoy.year * 12 + hoy.month))


def leer_meta(db: Session, meta: Meta) -> MetaLeer:
    objetivo = Decimal(meta.monto_objetivo)
    guardado = ahorrado(db, meta.id)
    cumplida = guardado >= objetivo
    faltante = max(objetivo - guardado, CERO)
    hoy = tiempo.hoy()
    cuota = None
    if not cumplida and meta.fecha_objetivo and meta.fecha_objetivo > hoy:
        cuota = (faltante / meses_restantes(meta.fecha_objetivo, hoy)).quantize(CENTAVOS)
    return MetaLeer(
        id=meta.id, nombre=meta.nombre, monto_objetivo=objetivo, fecha_objetivo=meta.fecha_objetivo,
        icono=meta.icono, color=meta.color, archivada=meta.archivada, creada_en=meta.creada_en,
        ahorrado=guardado, faltante=faltante.quantize(CENTAVOS),
        porcentaje=(guardado * 100 / objetivo).quantize(CENTAVOS),
        cumplida=cumplida, cuota_mensual_sugerida=cuota,
    )


def detalle_meta(db: Session, meta: Meta) -> MetaDetalle:
    aportes = db.scalars(
        select(AporteMeta).where(AporteMeta.meta_id == meta.id).order_by(AporteMeta.fecha.desc(), AporteMeta.id.desc())
    ).all()
    return MetaDetalle(**leer_meta(db, meta).model_dump(), aportes=[AporteLeer.model_validate(a) for a in aportes])


def avisar_si_se_cumplio(db: Session, meta: Meta, estaba_cumplida: bool) -> None:
    """Crea un aviso la vez que la meta pasa de "en curso" a "cumplida" (sea por ahorrar más o por bajar el objetivo)."""
    if not estaba_cumplida and ahorrado(db, meta.id) >= meta.monto_objetivo:
        db.add(Notificacion(
            usuario_id=meta.usuario_id, tipo=TipoNotificacion.INFO,
            mensaje=f"¡Meta cumplida! Llegaste a {cop(meta.monto_objetivo)} en «{meta.nombre}»",
        ))
