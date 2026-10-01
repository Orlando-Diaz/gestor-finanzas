from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import Frecuencia, TipoTransaccion
from app.schemas.transaccion import CategoriaResumen, CuentaResumen
from app.services.recurrentes import fecha_quincenal_valida


class RecurrenteCrear(BaseModel):
    """`proxima_fecha` es la fecha del primer movimiento. Si ya pasó, al crearla se registran
    de una vez los movimientos pendientes hasta hoy."""

    model_config = ConfigDict(str_strip_whitespace=True)

    tipo: TipoTransaccion
    monto: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    cuenta_id: int
    categoria_id: int
    nota: str | None = Field(default=None, max_length=200)
    frecuencia: Frecuencia
    proxima_fecha: date
    fecha_fin: date | None = None

    @model_validator(mode="after")
    def validar(self):
        if self.tipo == TipoTransaccion.TRANSFERENCIA:
            raise ValueError("Las transferencias no pueden ser recurrentes")
        if self.frecuencia == Frecuencia.QUINCENAL and not fecha_quincenal_valida(self.proxima_fecha):
            raise ValueError("Una recurrente QUINCENAL cae el día 15 o el último día del mes")
        if self.fecha_fin is not None and self.fecha_fin < self.proxima_fecha:
            raise ValueError("fecha_fin no puede ser anterior a proxima_fecha")
        return self


class RecurrenteActualizar(BaseModel):
    """El tipo no se cambia. Para pausarla: activa=false."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    monto: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    cuenta_id: int | None = None
    categoria_id: int | None = None
    nota: str | None = Field(default=None, max_length=200)
    frecuencia: Frecuencia | None = None
    proxima_fecha: date | None = None
    fecha_fin: date | None = None  # null quita la fecha de fin
    activa: bool | None = None


class RecurrenteLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: TipoTransaccion
    monto: Decimal
    nota: str | None
    frecuencia: Frecuencia
    proxima_fecha: date
    fecha_fin: date | None
    activa: bool
    cuenta: CuentaResumen
    categoria: CategoriaResumen


class ResultadoProcesar(BaseModel):
    generadas: int
