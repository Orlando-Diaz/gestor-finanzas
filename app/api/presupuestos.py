from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import AnioQ, DbDep, MesQ, UsuarioActual, periodo_o_actual
from app.models import Presupuesto, TipoTransaccion
from app.schemas.presupuesto import CopiarPresupuestos, PresupuestoActualizar, PresupuestoCrear, PresupuestoLeer
from app.services.presupuestos import calcular_progreso, evaluar_presupuesto, gastado_en_periodo, reiniciar_alertas
from app.services.validaciones import categoria_valida, categorias_ocultas

router = APIRouter(prefix="/presupuestos", tags=["Presupuestos"])


def _leer(db, p: Presupuesto) -> PresupuestoLeer:
    progreso = calcular_progreso(p, gastado_en_periodo(db, p.usuario_id, p.categoria_id, p.anio, p.mes))
    return PresupuestoLeer(
        id=p.id, categoria=p.categoria, mes=p.mes, anio=p.anio,
        monto_limite=p.monto_limite, umbral_alerta=p.umbral_alerta, **progreso,
    )


def _obtener(db, usuario, presupuesto_id: int) -> Presupuesto:
    p = db.scalar(select(Presupuesto).where(Presupuesto.id == presupuesto_id, Presupuesto.usuario_id == usuario.id))
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Presupuesto no encontrado")
    return p


def _duplicado() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, "Ya tienes un presupuesto para esa categoría en ese mes")


@router.get("", response_model=list[PresupuestoLeer])
def listar(db: DbDep, usuario: UsuarioActual, anio: AnioQ = None, mes: MesQ = None):
    """Presupuestos de un mes (por defecto, el actual) con lo gastado, lo que queda y su estado."""
    anio, mes = periodo_o_actual(anio, mes)
    filas = db.scalars(
        select(Presupuesto).where(
            Presupuesto.usuario_id == usuario.id, Presupuesto.anio == anio, Presupuesto.mes == mes
        )
    ).all()
    return sorted((_leer(db, p) for p in filas), key=lambda x: x.categoria.nombre)


@router.post("", response_model=PresupuestoLeer, status_code=status.HTTP_201_CREATED)
def crear(datos: PresupuestoCrear, db: DbDep, usuario: UsuarioActual):
    categoria_valida(db, usuario, datos.categoria_id, TipoTransaccion.GASTO)
    if db.scalar(
        select(Presupuesto.id).where(
            Presupuesto.usuario_id == usuario.id,
            Presupuesto.categoria_id == datos.categoria_id,
            Presupuesto.anio == datos.anio,
            Presupuesto.mes == datos.mes,
        )
    ):
        raise _duplicado()
    p = Presupuesto(usuario_id=usuario.id, **datos.model_dump())
    db.add(p)
    try:
        db.flush()
        evaluar_presupuesto(db, p)  # si ya llevas gastado de más, avisa de una vez
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _duplicado()
    db.refresh(p)
    return _leer(db, p)


@router.post("/copiar", response_model=list[PresupuestoLeer], status_code=status.HTTP_201_CREATED)
def copiar(datos: CopiarPresupuestos, db: DbDep, usuario: UsuarioActual):
    """Copia los presupuestos de un mes a otro (omite las categorías que ya tienen uno o están archivadas)."""
    origen = db.scalars(
        select(Presupuesto).where(
            Presupuesto.usuario_id == usuario.id,
            Presupuesto.anio == datos.desde_anio,
            Presupuesto.mes == datos.desde_mes,
        )
    ).all()
    if not origen:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El mes de origen no tiene presupuestos")
    existentes = set(
        db.scalars(
            select(Presupuesto.categoria_id).where(
                Presupuesto.usuario_id == usuario.id,
                Presupuesto.anio == datos.a_anio,
                Presupuesto.mes == datos.a_mes,
            )
        )
    )
    ocultas = categorias_ocultas(db, usuario)
    nuevos = [
        Presupuesto(
            usuario_id=usuario.id, categoria_id=o.categoria_id, monto_limite=o.monto_limite,
            umbral_alerta=o.umbral_alerta, anio=datos.a_anio, mes=datos.a_mes,
        )
        for o in origen
        if o.categoria_id not in existentes and not o.categoria.archivada and o.categoria_id not in ocultas
    ]
    db.add_all(nuevos)
    db.flush()
    for p in nuevos:
        evaluar_presupuesto(db, p)
    db.commit()
    for p in nuevos:
        db.refresh(p)
    return sorted((_leer(db, p) for p in nuevos), key=lambda x: x.categoria.nombre)


@router.get("/{presupuesto_id}", response_model=PresupuestoLeer)
def detalle(presupuesto_id: int, db: DbDep, usuario: UsuarioActual):
    return _leer(db, _obtener(db, usuario, presupuesto_id))


@router.patch("/{presupuesto_id}", response_model=PresupuestoLeer)
def actualizar(presupuesto_id: int, datos: PresupuestoActualizar, db: DbDep, usuario: UsuarioActual):
    p = _obtener(db, usuario, presupuesto_id)
    cambios = datos.model_dump(exclude_unset=True)
    if any(v is None for v in cambios.values()):
        raise HTTPException(422, "monto_limite y umbral_alerta no pueden ser nulos")
    for campo, valor in cambios.items():
        setattr(p, campo, valor)
    if cambios:
        reiniciar_alertas(db, p.id)  # con el límite nuevo las alertas pueden volver a dispararse
        db.flush()
        evaluar_presupuesto(db, p)
    db.commit()
    db.refresh(p)
    return _leer(db, p)


@router.delete("/{presupuesto_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(presupuesto_id: int, db: DbDep, usuario: UsuarioActual):
    db.delete(_obtener(db, usuario, presupuesto_id))
    db.commit()
