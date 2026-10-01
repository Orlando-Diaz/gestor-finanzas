from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbDep, UsuarioActual
from app.models import Cuenta, Transaccion, TransaccionRecurrente
from app.schemas.cuenta import CuentaActualizar, CuentaConSaldo, CuentaCrear, CuentaLeer
from app.services.saldos import deltas_por_cuenta, saldo_actual

router = APIRouter(prefix="/cuentas", tags=["Cuentas"])


def _con_saldo(cuenta: Cuenta, deltas: dict[int, Decimal]) -> CuentaConSaldo:
    return CuentaConSaldo(
        **CuentaLeer.model_validate(cuenta).model_dump(),
        saldo_actual=saldo_actual(cuenta.saldo_inicial, deltas.get(cuenta.id)),
    )


def _obtener(db, usuario, cuenta_id: int) -> Cuenta:
    cuenta = db.scalar(select(Cuenta).where(Cuenta.id == cuenta_id, Cuenta.usuario_id == usuario.id))
    if cuenta is None:  # también cubre cuentas de otros usuarios: no se revela que existen
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cuenta no encontrada")
    return cuenta


def _validar_nombre_libre(db, usuario, nombre: str, excluir_id: int | None = None):
    consulta = select(Cuenta.id).where(
        Cuenta.usuario_id == usuario.id, func.lower(Cuenta.nombre) == nombre.lower()
    )
    if excluir_id is not None:
        consulta = consulta.where(Cuenta.id != excluir_id)
    if db.scalar(consulta):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya tienes una cuenta con ese nombre")


@router.get("", response_model=list[CuentaConSaldo])
def listar(db: DbDep, usuario: UsuarioActual, incluir_archivadas: bool = False):
    consulta = select(Cuenta).where(Cuenta.usuario_id == usuario.id).order_by(Cuenta.id)
    if not incluir_archivadas:
        consulta = consulta.where(Cuenta.archivada.is_(False))
    deltas = deltas_por_cuenta(db, usuario.id)
    return [_con_saldo(c, deltas) for c in db.scalars(consulta)]


@router.post("", response_model=CuentaConSaldo, status_code=status.HTTP_201_CREATED)
def crear(datos: CuentaCrear, db: DbDep, usuario: UsuarioActual):
    _validar_nombre_libre(db, usuario, datos.nombre)
    cuenta = Cuenta(usuario_id=usuario.id, **datos.model_dump())
    db.add(cuenta)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya tienes una cuenta con ese nombre")
    db.refresh(cuenta)
    return _con_saldo(cuenta, {})


@router.get("/{cuenta_id}", response_model=CuentaConSaldo)
def detalle(cuenta_id: int, db: DbDep, usuario: UsuarioActual):
    cuenta = _obtener(db, usuario, cuenta_id)
    return _con_saldo(cuenta, deltas_por_cuenta(db, usuario.id))


@router.patch("/{cuenta_id}", response_model=CuentaConSaldo)
def actualizar(cuenta_id: int, datos: CuentaActualizar, db: DbDep, usuario: UsuarioActual):
    cuenta = _obtener(db, usuario, cuenta_id)
    cambios = datos.model_dump(exclude_unset=True)
    for campo in ("nombre", "tipo", "saldo_inicial", "archivada"):
        if campo in cambios and cambios[campo] is None:
            raise HTTPException(422, f"{campo} no puede ser nulo")
    if "nombre" in cambios:
        _validar_nombre_libre(db, usuario, cambios["nombre"], excluir_id=cuenta.id)
    for campo, valor in cambios.items():
        setattr(cuenta, campo, valor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya tienes una cuenta con ese nombre")
    db.refresh(cuenta)
    return _con_saldo(cuenta, deltas_por_cuenta(db, usuario.id))


@router.delete("/{cuenta_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(cuenta_id: int, db: DbDep, usuario: UsuarioActual):
    """Solo se borra una cuenta sin movimientos; si ya tiene historial, se archiva."""
    cuenta = _obtener(db, usuario, cuenta_id)
    con_movimientos = db.scalar(
        select(Transaccion.id)
        .where(or_(Transaccion.cuenta_id == cuenta.id, Transaccion.cuenta_destino_id == cuenta.id))
        .limit(1)
    ) or db.scalar(select(TransaccionRecurrente.id).where(TransaccionRecurrente.cuenta_id == cuenta.id).limit(1))
    if con_movimientos:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "La cuenta tiene movimientos; archívala (PATCH archivada=true) en lugar de borrarla",
        )
    db.delete(cuenta)
    db.commit()
