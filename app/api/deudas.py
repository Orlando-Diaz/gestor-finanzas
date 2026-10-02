from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import DbDep, UsuarioActual
from app.core import tiempo
from app.models import Deuda, PagoDeuda, TipoDeuda
from app.schemas.deuda import DeudaActualizar, DeudaCrear, DeudaDetalle, DeudaLeer, PagoCrear, ResumenDeudas
from app.services.deudas import detalle_deuda, leer_deuda, pagado
from app.services.validaciones import error_422

router = APIRouter(prefix="/deudas", tags=["Deudas"])

CERO = Decimal("0.00")


def _obtener(db, usuario, deuda_id: int) -> Deuda:
    deuda = db.scalar(select(Deuda).where(Deuda.id == deuda_id, Deuda.usuario_id == usuario.id))
    if deuda is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Deuda no encontrada")
    return deuda


def _todas(db, usuario) -> list[DeudaLeer]:
    return [leer_deuda(db, d) for d in db.scalars(select(Deuda).where(Deuda.usuario_id == usuario.id)).all()]


@router.get("", response_model=list[DeudaLeer])
def listar(
    db: DbDep,
    usuario: UsuarioActual,
    estado: Annotated[Literal["pendientes", "saldadas", "todas"], Query()] = "pendientes",
    tipo: TipoDeuda | None = None,
):
    """Las que vencen antes van primero; las que no tienen vencimiento, después."""
    deudas = [
        d for d in _todas(db, usuario)
        if (tipo is None or d.tipo == tipo)
        and (estado == "todas" or d.saldada == (estado == "saldadas"))
    ]
    return sorted(deudas, key=lambda d: (d.fecha_vencimiento is None, d.fecha_vencimiento or d.fecha, -d.id))


@router.get("/resumen", response_model=ResumenDeudas)
def resumen(db: DbDep, usuario: UsuarioActual):
    """Cuánto te deben, cuánto debes y cuántas están vencidas (solo lo pendiente)."""
    pendientes = [d for d in _todas(db, usuario) if not d.saldada]
    me_deben = [d for d in pendientes if d.tipo == TipoDeuda.ME_DEBEN]
    debo = [d for d in pendientes if d.tipo == TipoDeuda.DEBO]
    total_me_deben = sum((d.pendiente for d in me_deben), start=CERO)
    total_debo = sum((d.pendiente for d in debo), start=CERO)
    return ResumenDeudas(
        me_deben=total_me_deben, debo=total_debo, neto=total_me_deben - total_debo,
        cantidad_me_deben=len(me_deben), cantidad_debo=len(debo), vencidas=sum(1 for d in pendientes if d.vencida),
    )


@router.post("", response_model=DeudaDetalle, status_code=status.HTTP_201_CREATED)
def crear(datos: DeudaCrear, db: DbDep, usuario: UsuarioActual):
    valores = datos.model_dump()
    valores["fecha"] = datos.fecha or tiempo.hoy()
    if valores["fecha_vencimiento"] and valores["fecha_vencimiento"] < valores["fecha"]:
        raise error_422("La fecha de vencimiento no puede ser anterior a la fecha de la deuda")
    deuda = Deuda(usuario_id=usuario.id, **valores)
    db.add(deuda)
    db.commit()
    db.refresh(deuda)
    return detalle_deuda(db, deuda)


@router.get("/{deuda_id}", response_model=DeudaDetalle)
def detalle(deuda_id: int, db: DbDep, usuario: UsuarioActual):
    return detalle_deuda(db, _obtener(db, usuario, deuda_id))


@router.patch("/{deuda_id}", response_model=DeudaDetalle)
def actualizar(deuda_id: int, datos: DeudaActualizar, db: DbDep, usuario: UsuarioActual):
    deuda = _obtener(db, usuario, deuda_id)
    cambios = datos.model_dump(exclude_unset=True)
    for campo in ("persona", "monto_total"):
        if campo in cambios and cambios[campo] is None:
            raise error_422(f"{campo} no puede ser nulo")
    if "monto_total" in cambios and cambios["monto_total"] < pagado(db, deuda.id):
        raise error_422("El total no puede ser menor a lo que ya se ha pagado")
    vencimiento = cambios.get("fecha_vencimiento", deuda.fecha_vencimiento)
    if vencimiento and vencimiento < deuda.fecha:
        raise error_422("La fecha de vencimiento no puede ser anterior a la fecha de la deuda")
    for campo, valor in cambios.items():
        setattr(deuda, campo, valor)
    db.commit()
    db.refresh(deuda)
    return detalle_deuda(db, deuda)


@router.delete("/{deuda_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(deuda_id: int, db: DbDep, usuario: UsuarioActual):
    """Borra la deuda y sus pagos."""
    db.delete(_obtener(db, usuario, deuda_id))
    db.commit()


@router.post("/{deuda_id}/pagos", response_model=DeudaDetalle, status_code=status.HTTP_201_CREATED)
def registrar_pago(deuda_id: int, datos: PagoCrear, db: DbDep, usuario: UsuarioActual):
    """Un abono. No puede superar lo que falta por pagar."""
    deuda = _obtener(db, usuario, deuda_id)
    pendiente = deuda.monto_total - pagado(db, deuda.id)
    if datos.monto > pendiente:
        raise error_422(f"El pago supera lo que falta por pagar ({pendiente})")
    db.add(PagoDeuda(deuda_id=deuda.id, monto=datos.monto, fecha=datos.fecha or tiempo.hoy(), nota=datos.nota))
    db.commit()
    db.refresh(deuda)
    return detalle_deuda(db, deuda)


@router.delete("/{deuda_id}/pagos/{pago_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_pago(deuda_id: int, pago_id: int, db: DbDep, usuario: UsuarioActual):
    deuda = _obtener(db, usuario, deuda_id)
    pago = db.scalar(select(PagoDeuda).where(PagoDeuda.id == pago_id, PagoDeuda.deuda_id == deuda.id))
    if pago is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pago no encontrado")
    db.delete(pago)
    db.commit()
