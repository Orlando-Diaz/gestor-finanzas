import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbDep, UsuarioActual
from app.core.config import settings
from app.core.security import HASH_FALSO, crear_token, hashear_password, verificar_password
from app.models import Cuenta, TipoCuenta, TransaccionRecurrente, Usuario
from app.schemas.usuario import CambiarPassword, EliminarCuenta, Token, UsuarioActualizar, UsuarioCrear, UsuarioLeer
from app.services.recurrentes import procesar_recurrentes

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/registro", response_model=UsuarioLeer, status_code=status.HTTP_201_CREATED)
def registro(datos: UsuarioCrear, db: DbDep):
    email = datos.email.lower()
    if db.scalar(select(Usuario.id).where(Usuario.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una cuenta con ese correo")

    usuario = Usuario(
        nombre=datos.nombre.strip(),
        email=email,
        password_hash=hashear_password(datos.password),
        moneda_por_defecto=settings.moneda_por_defecto,
    )
    # Todo usuario arranca con una cuenta "Efectivo" para poder registrar de una vez
    usuario.cuentas.append(Cuenta(nombre="Efectivo", tipo=TipoCuenta.EFECTIVO))
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError:  # dos registros simultáneos con el mismo correo
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una cuenta con ese correo")
    db.refresh(usuario)
    return usuario


@router.post("/login", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbDep):
    """El campo `username` del formulario OAuth2 es el correo."""
    usuario = db.scalar(select(Usuario).where(Usuario.email == form.username.lower()))
    # Siempre se verifica un hash, exista o no el usuario (evita revelar correos registrados)
    password_ok = verificar_password(form.password, usuario.password_hash if usuario else HASH_FALSO)
    if not usuario or not password_ok or not usuario.activo:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    usuario_id, huella = usuario.id, usuario.password_hash
    try:  # al entrar se registran los movimientos recurrentes que vencieron mientras no estabas
        procesar_recurrentes(db, usuario_id)
    except Exception:  # un fallo aquí nunca debe impedir iniciar sesión
        db.rollback()
        log.exception("No se pudieron procesar las recurrentes del usuario %s", usuario_id)
    return Token(access_token=crear_token(usuario_id, huella))


@router.get("/me", response_model=UsuarioLeer)
def me(usuario: UsuarioActual):
    return usuario


@router.patch("/me", response_model=UsuarioLeer)
def actualizar_perfil(datos: UsuarioActualizar, db: DbDep, usuario: UsuarioActual):
    usuario.nombre = datos.nombre
    db.commit()
    db.refresh(usuario)
    return usuario


@router.post("/cambiar-password", status_code=status.HTTP_204_NO_CONTENT)
def cambiar_password(datos: CambiarPassword, db: DbDep, usuario: UsuarioActual):
    """Cierra todas las sesiones abiertas: hay que volver a iniciar sesión con la clave nueva."""
    if not verificar_password(datos.password_actual, usuario.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La contraseña actual no es correcta")
    usuario.password_hash = hashear_password(datos.password_nueva)
    db.commit()


@router.post("/eliminar-cuenta", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_cuenta(datos: EliminarCuenta, db: DbDep, usuario: UsuarioActual):
    """Borra el usuario y TODOS sus datos (cuentas, movimientos, categorías, presupuestos...). No se puede deshacer."""
    if not verificar_password(datos.password, usuario.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La contraseña no es correcta")
    # las recurrentes apuntan a cuentas y categorías: se borran primero para no bloquear el resto
    db.execute(delete(TransaccionRecurrente).where(TransaccionRecurrente.usuario_id == usuario.id))
    db.delete(usuario)
    db.commit()
