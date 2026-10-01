import enum


class TipoCuenta(str, enum.Enum):
    EFECTIVO = "EFECTIVO"
    BANCARIA = "BANCARIA"
    BILLETERA_DIGITAL = "BILLETERA_DIGITAL"  # Nequi, Daviplata...
    TARJETA_CREDITO = "TARJETA_CREDITO"


class TipoCategoria(str, enum.Enum):
    INGRESO = "INGRESO"
    GASTO = "GASTO"


class TipoTransaccion(str, enum.Enum):
    INGRESO = "INGRESO"
    GASTO = "GASTO"
    TRANSFERENCIA = "TRANSFERENCIA"


class Frecuencia(str, enum.Enum):
    SEMANAL = "SEMANAL"
    QUINCENAL = "QUINCENAL"
    MENSUAL = "MENSUAL"
    ANUAL = "ANUAL"


class TipoNotificacion(str, enum.Enum):
    PRESUPUESTO_UMBRAL = "PRESUPUESTO_UMBRAL"  # llegaste al % de alerta
    PRESUPUESTO_EXCEDIDO = "PRESUPUESTO_EXCEDIDO"
    RECURRENTE_REGISTRADA = "RECURRENTE_REGISTRADA"
    INFO = "INFO"
