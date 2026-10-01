# Importar todos los modelos aquí para que Base.metadata los conozca.
from app.models.categoria import Categoria
from app.models.cuenta import Cuenta
from app.models.enums import (
    Frecuencia,
    TipoCategoria,
    TipoCuenta,
    TipoNotificacion,
    TipoTransaccion,
)
from app.models.notificacion import Notificacion
from app.models.presupuesto import Presupuesto
from app.models.recurrente import TransaccionRecurrente
from app.models.transaccion import Transaccion
from app.models.usuario import Usuario

__all__ = [
    "Categoria",
    "Cuenta",
    "Frecuencia",
    "Notificacion",
    "Presupuesto",
    "TipoCategoria",
    "TipoCuenta",
    "TipoNotificacion",
    "TipoTransaccion",
    "Transaccion",
    "TransaccionRecurrente",
    "Usuario",
]
