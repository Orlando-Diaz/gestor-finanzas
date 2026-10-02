from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import tiempo
from app.models import Deuda, PagoDeuda
from app.schemas.deuda import DeudaDetalle, DeudaLeer, PagoLeer
from app.services.saldos import CENTAVOS

CERO = Decimal("0.00")


def pagado(db: Session, deuda_id: int) -> Decimal:
    total = db.scalar(select(func.coalesce(func.sum(PagoDeuda.monto), 0)).where(PagoDeuda.deuda_id == deuda_id))
    return Decimal(str(total)).quantize(CENTAVOS)


def leer_deuda(db: Session, deuda: Deuda) -> DeudaLeer:
    total = Decimal(deuda.monto_total)
    abonado = pagado(db, deuda.id)
    pendiente = max(total - abonado, CERO)
    saldada = pendiente == 0
    return DeudaLeer(
        id=deuda.id, tipo=deuda.tipo, persona=deuda.persona, descripcion=deuda.descripcion,
        monto_total=total, fecha=deuda.fecha, fecha_vencimiento=deuda.fecha_vencimiento, creada_en=deuda.creada_en,
        pagado=abonado, pendiente=pendiente.quantize(CENTAVOS),
        porcentaje=(min(abonado, total) * 100 / total).quantize(CENTAVOS),
        saldada=saldada,
        vencida=(not saldada) and deuda.fecha_vencimiento is not None and deuda.fecha_vencimiento < tiempo.hoy(),
    )


def detalle_deuda(db: Session, deuda: Deuda) -> DeudaDetalle:
    pagos = db.scalars(
        select(PagoDeuda).where(PagoDeuda.deuda_id == deuda.id).order_by(PagoDeuda.fecha.desc(), PagoDeuda.id.desc())
    ).all()
    return DeudaDetalle(**leer_deuda(db, deuda).model_dump(), pagos=[PagoLeer.model_validate(p) for p in pagos])
