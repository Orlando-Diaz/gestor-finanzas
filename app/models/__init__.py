# Importar todos los modelos aquí para que Base.metadata los conozca.
from app.models.categoria import Categoria
from app.models.cuenta import Cuenta
from app.models.deuda import Deuda, PagoDeuda
from app.models.enums import (
    Frecuencia,
    TipoAporte,
    TipoCategoria,
    TipoCuenta,
    TipoDeuda,
    TipoNotificacion,
    TipoTransaccion,
)
from app.models.meta import AporteMeta, Meta
from app.models.notificacion import Notificacion
from app.models.presupuesto import Presupuesto
from app.models.recurrente import TransaccionRecurrente
from app.models.transaccion import Transaccion
from app.models.usuario import Usuario

__all__ = [
    "AporteMeta",
    "Categoria",
    "Cuenta",
    "Deuda",
    "Frecuencia",
    "Meta",
    "Notificacion",
    "PagoDeuda",
    "Presupuesto",
    "TipoAporte",
    "TipoCategoria",
    "TipoCuenta",
    "TipoDeuda",
    "TipoNotificacion",
    "TipoTransaccion",
    "Transaccion",
    "TransaccionRecurrente",
    "Usuario",
]
