from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select, update

from app.api.deps import DbDep, UsuarioActual
from app.models import Notificacion
from app.schemas.notificacion import ConteoNotificaciones, NotificacionLeer

router = APIRouter(prefix="/notificaciones", tags=["Notificaciones"])


def _obtener(db, usuario, notificacion_id: int) -> Notificacion:
    n = db.scalar(select(Notificacion).where(Notificacion.id == notificacion_id, Notificacion.usuario_id == usuario.id))
    if n is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notificación no encontrada")
    return n


@router.get("", response_model=list[NotificacionLeer])
def listar(
    db: DbDep,
    usuario: UsuarioActual,
    solo_no_leidas: bool = False,
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Las más recientes primero."""
    consulta = select(Notificacion).where(Notificacion.usuario_id == usuario.id)
    if solo_no_leidas:
        consulta = consulta.where(Notificacion.leida.is_(False))
    return db.scalars(consulta.order_by(Notificacion.creada_en.desc(), Notificacion.id.desc()).limit(limite)).all()


@router.get("/conteo", response_model=ConteoNotificaciones)
def conteo(db: DbDep, usuario: UsuarioActual):
    """Para el globito rojo de la campana."""
    n = db.scalar(
        select(func.count()).select_from(Notificacion).where(
            Notificacion.usuario_id == usuario.id, Notificacion.leida.is_(False)
        )
    )
    return ConteoNotificaciones(no_leidas=n)


@router.post("/leer-todas", status_code=status.HTTP_204_NO_CONTENT)
def leer_todas(db: DbDep, usuario: UsuarioActual):
    db.execute(
        update(Notificacion)
        .where(Notificacion.usuario_id == usuario.id, Notificacion.leida.is_(False))
        .values(leida=True)
    )
    db.commit()


@router.patch("/{notificacion_id}/leer", response_model=NotificacionLeer)
def marcar_leida(notificacion_id: int, db: DbDep, usuario: UsuarioActual):
    n = _obtener(db, usuario, notificacion_id)
    n.leida = True
    db.commit()
    db.refresh(n)
    return n


@router.delete("/{notificacion_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(notificacion_id: int, db: DbDep, usuario: UsuarioActual):
    db.delete(_obtener(db, usuario, notificacion_id))
    db.commit()
