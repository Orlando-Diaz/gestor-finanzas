import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

ALGORITMO = "HS256"


def hashear_password(password: str) -> str:
    sal = bcrypt.gensalt(rounds=settings.bcrypt_rounds)
    return bcrypt.hashpw(password.encode("utf-8"), sal).decode("utf-8")


def verificar_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# Hash de relleno: permite gastar el mismo tiempo cuando el email no existe,
# así el login no revela qué correos están registrados.
HASH_FALSO = hashear_password("relleno-no-es-una-clave-real")


def huella_password(password_hash: str) -> str:
    """Identificador corto del hash actual: cambia cuando cambia la contraseña."""
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()[:16]


def crear_token(usuario_id: int, password_hash: str) -> str:
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario_id),
        "ph": huella_password(password_hash),
        "iat": ahora,
        "exp": ahora + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITMO)


def leer_token(token: str) -> tuple[int, str] | None:
    """Devuelve (id de usuario, huella de contraseña), o None si el token es inválido o expiró."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITMO])
        return int(payload["sub"]), str(payload["ph"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
