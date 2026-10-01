from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbDep, UsuarioActual
from app.core.config import settings
from app.core.security import HASH_FALSO, crear_token, hashear_password, verificar_password
from app.models import Cuenta, TipoCuenta, Usuario
from app.schemas.usuario import Token, UsuarioCrear, UsuarioLeer

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
    return Token(access_token=crear_token(usuario.id))


@router.get("/me", response_model=UsuarioLeer)
def me(usuario: UsuarioActual):
    return usuario
