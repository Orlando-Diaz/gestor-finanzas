from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import DbDep, UsuarioActual
from app.core import tiempo
from app.models import AporteMeta, Meta, TipoAporte
from app.schemas.meta import AporteCrear, MetaActualizar, MetaCrear, MetaDetalle, MetaLeer
from app.services.metas import ahorrado, avisar_si_se_cumplio, detalle_meta, leer_meta
from app.services.validaciones import error_422

router = APIRouter(prefix="/metas", tags=["Metas de ahorro"])


def _obtener(db, usuario, meta_id: int) -> Meta:
    meta = db.scalar(select(Meta).where(Meta.id == meta_id, Meta.usuario_id == usuario.id))
    if meta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meta no encontrada")
    return meta


@router.get("", response_model=list[MetaLeer])
def listar(db: DbDep, usuario: UsuarioActual, incluir_archivadas: Annotated[bool, Query()] = False):
    """Metas con su progreso. Las que están en curso primero, las cumplidas al final."""
    consulta = select(Meta).where(Meta.usuario_id == usuario.id)
    if not incluir_archivadas:
        consulta = consulta.where(Meta.archivada.is_(False))
    metas = [leer_meta(db, m) for m in db.scalars(consulta.order_by(Meta.id)).all()]
    return sorted(metas, key=lambda m: (m.cumplida, m.fecha_objetivo is None, m.fecha_objetivo or tiempo.hoy(), m.id))


@router.post("", response_model=MetaDetalle, status_code=status.HTTP_201_CREATED)
def crear(datos: MetaCrear, db: DbDep, usuario: UsuarioActual):
    meta = Meta(usuario_id=usuario.id, **datos.model_dump())
    db.add(meta)
    db.commit()
    db.refresh(meta)
    return detalle_meta(db, meta)


@router.get("/{meta_id}", response_model=MetaDetalle)
def detalle(meta_id: int, db: DbDep, usuario: UsuarioActual):
    return detalle_meta(db, _obtener(db, usuario, meta_id))


@router.patch("/{meta_id}", response_model=MetaDetalle)
def actualizar(meta_id: int, datos: MetaActualizar, db: DbDep, usuario: UsuarioActual):
    meta = _obtener(db, usuario, meta_id)
    cambios = datos.model_dump(exclude_unset=True)
    for campo in ("nombre", "monto_objetivo", "archivada"):
        if campo in cambios and cambios[campo] is None:
            raise error_422(f"{campo} no puede ser nulo")
    estaba_cumplida = ahorrado(db, meta.id) >= meta.monto_objetivo
    for campo, valor in cambios.items():
        setattr(meta, campo, valor)
    db.flush()
    if "monto_objetivo" in cambios:  # bajar el objetivo puede dejar la meta cumplida
        avisar_si_se_cumplio(db, meta, estaba_cumplida)
    db.commit()
    db.refresh(meta)
    return detalle_meta(db, meta)


@router.delete("/{meta_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(meta_id: int, db: DbDep, usuario: UsuarioActual):
    """Borra la meta y todos sus aportes. Para conservarla sin verla, archívala."""
    db.delete(_obtener(db, usuario, meta_id))
    db.commit()


@router.post("/{meta_id}/aportes", response_model=MetaDetalle, status_code=status.HTTP_201_CREATED)
def aportar(meta_id: int, datos: AporteCrear, db: DbDep, usuario: UsuarioActual):
    """Aparta plata para la meta (`APORTE`) o saca plata de ella (`RETIRO`)."""
    meta = _obtener(db, usuario, meta_id)
    antes = ahorrado(db, meta.id)
    estaba_cumplida = antes >= meta.monto_objetivo
    if datos.tipo == TipoAporte.RETIRO and datos.monto > antes:
        raise error_422(f"No puedes retirar más de lo que has ahorrado ({antes})")
    db.add(AporteMeta(meta_id=meta.id, tipo=datos.tipo, monto=datos.monto, fecha=datos.fecha or tiempo.hoy(), nota=datos.nota))
    db.flush()
    if datos.tipo == TipoAporte.APORTE:
        avisar_si_se_cumplio(db, meta, estaba_cumplida)
    db.commit()
    db.refresh(meta)
    return detalle_meta(db, meta)


@router.delete("/{meta_id}/aportes/{aporte_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_aporte(meta_id: int, aporte_id: int, db: DbDep, usuario: UsuarioActual):
    meta = _obtener(db, usuario, meta_id)
    aporte = db.scalar(select(AporteMeta).where(AporteMeta.id == aporte_id, AporteMeta.meta_id == meta.id))
    if aporte is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aporte no encontrado")
    quedaria = ahorrado(db, meta.id) + (aporte.monto if aporte.tipo == TipoAporte.RETIRO else -aporte.monto)
    if quedaria < 0:
        raise error_422("No puedes borrar este aporte: la meta quedaría con saldo negativo")
    db.delete(aporte)
    db.commit()
