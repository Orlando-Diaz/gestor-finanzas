from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import DbDep, UsuarioActual
from app.core import tiempo
from app.models import Frecuencia, TipoTransaccion, TransaccionRecurrente
from app.schemas.recurrente import RecurrenteActualizar, RecurrenteCrear, RecurrenteLeer, ResultadoProcesar
from app.services.recurrentes import fecha_quincenal_valida, procesar_recurrentes
from app.services.validaciones import categoria_valida, cuenta_valida, error_422

router = APIRouter(prefix="/recurrentes", tags=["Recurrentes"])

R = TransaccionRecurrente


def _obtener(db, usuario, recurrente_id: int) -> R:
    r = db.scalar(select(R).where(R.id == recurrente_id, R.usuario_id == usuario.id))
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Movimiento recurrente no encontrado")
    return r


@router.get("", response_model=list[RecurrenteLeer])
def listar(db: DbDep, usuario: UsuarioActual, solo_activas: bool = False):
    """Primero las activas, por orden de próxima fecha."""
    consulta = select(R).where(R.usuario_id == usuario.id).order_by(R.activa.desc(), R.proxima_fecha, R.id)
    if solo_activas:
        consulta = consulta.where(R.activa.is_(True))
    return db.scalars(consulta).all()


@router.post("", response_model=RecurrenteLeer, status_code=status.HTTP_201_CREATED)
def crear(datos: RecurrenteCrear, db: DbDep, usuario: UsuarioActual):
    cuenta_valida(db, usuario, datos.cuenta_id)
    categoria_valida(db, usuario, datos.categoria_id, datos.tipo)
    r = R(usuario_id=usuario.id, dia_ancla=datos.proxima_fecha.day, **datos.model_dump())
    db.add(r)
    db.commit()
    procesar_recurrentes(db, usuario.id)  # si empieza hoy o antes, se registra de una vez
    db.refresh(r)
    return r


@router.post("/procesar", response_model=ResultadoProcesar)
def procesar(db: DbDep, usuario: UsuarioActual):
    """Registra los movimientos recurrentes vencidos. Es seguro llamarlo varias veces."""
    return ResultadoProcesar(generadas=procesar_recurrentes(db, usuario.id))


@router.get("/{recurrente_id}", response_model=RecurrenteLeer)
def detalle(recurrente_id: int, db: DbDep, usuario: UsuarioActual):
    return _obtener(db, usuario, recurrente_id)


@router.patch("/{recurrente_id}", response_model=RecurrenteLeer)
def actualizar(recurrente_id: int, datos: RecurrenteActualizar, db: DbDep, usuario: UsuarioActual):
    r = _obtener(db, usuario, recurrente_id)
    cambios = datos.model_dump(exclude_unset=True)
    for campo in ("monto", "cuenta_id", "categoria_id", "frecuencia", "proxima_fecha", "activa"):
        if campo in cambios and cambios[campo] is None:
            raise error_422(f"{campo} no puede ser nulo")

    if "cuenta_id" in cambios and cambios["cuenta_id"] != r.cuenta_id:
        cuenta_valida(db, usuario, cambios["cuenta_id"])
    if "categoria_id" in cambios and cambios["categoria_id"] != r.categoria_id:
        categoria_valida(db, usuario, cambios["categoria_id"], r.tipo)

    # Reglas sobre el estado resultante
    frecuencia = cambios.get("frecuencia", r.frecuencia)
    proxima = cambios.get("proxima_fecha", r.proxima_fecha)
    fin = cambios["fecha_fin"] if "fecha_fin" in cambios else r.fecha_fin
    activa = cambios.get("activa", r.activa)
    if frecuencia == Frecuencia.QUINCENAL and not fecha_quincenal_valida(proxima):
        raise error_422("Una recurrente QUINCENAL cae el día 15 o el último día del mes")
    if activa and fin is not None and fin < proxima:
        raise error_422("fecha_fin no puede ser anterior a proxima_fecha")
    if activa and not r.activa and proxima < tiempo.hoy():
        # evita que al reactivar se registren de golpe todos los periodos que estuvo pausada
        raise error_422("Para reactivarla indica una proxima_fecha de hoy en adelante")

    for campo, valor in cambios.items():
        setattr(r, campo, valor)
    if "proxima_fecha" in cambios:
        r.dia_ancla = proxima.day
    db.commit()
    procesar_recurrentes(db, usuario.id)
    db.refresh(r)
    return r


@router.delete("/{recurrente_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(recurrente_id: int, db: DbDep, usuario: UsuarioActual):
    """Los movimientos que ya generó se conservan en el historial."""
    db.delete(_obtener(db, usuario, recurrente_id))
    db.commit()
