from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import huella_password, leer_token
from app.core.tiempo import hoy
from app.models import Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

DbDep = Annotated[Session, Depends(get_db)]


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DbDep) -> Usuario:
    no_autorizado = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    datos = leer_token(token)
    if datos is None:
        raise no_autorizado
    usuario_id, huella = datos
    usuario = db.get(Usuario, usuario_id)
    # la huella distingue los tokens emitidos antes de un cambio de contraseña
    if usuario is None or not usuario.activo or huella != huella_password(usuario.password_hash):
        raise no_autorizado
    return usuario


UsuarioActual = Annotated[Usuario, Depends(get_current_user)]


AnioQ = Annotated[int | None, Query(ge=2000, le=2100, description="Por defecto, el año actual")]
MesQ = Annotated[int | None, Query(ge=1, le=12, description="Por defecto, el mes actual")]


def periodo_o_actual(anio: int | None, mes: int | None) -> tuple[int, int]:
    """Valida el par anio/mes (juntos o ninguno) y usa el mes actual si no se enviaron."""
    if (anio is None) != (mes is None):
        raise HTTPException(422, "Envía 'anio' y 'mes' juntos, o ninguno para usar el mes actual")
    if anio is None:
        actual = hoy()
        return actual.year, actual.month
    return anio, mes
