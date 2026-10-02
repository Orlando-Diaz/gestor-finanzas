from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import TipoDeuda


class DeudaCrear(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    tipo: TipoDeuda
    persona: str = Field(min_length=1, max_length=100, description="Quién te debe o a quién le debes")
    descripcion: str | None = Field(default=None, max_length=255)
    monto_total: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    fecha: date | None = Field(default=None, description="Cuándo se prestó. Por defecto, hoy (hora de Colombia)")
    fecha_vencimiento: date | None = None

    @model_validator(mode="after")
    def vencimiento_posterior(self):
        if self.fecha and self.fecha_vencimiento and self.fecha_vencimiento < self.fecha:
            raise ValueError("La fecha de vencimiento no puede ser anterior a la fecha de la deuda")
        return self


class DeudaActualizar(BaseModel):
    """El tipo no se cambia. `fecha_vencimiento: null` quita el vencimiento."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    persona: str | None = Field(default=None, min_length=1, max_length=100)
    descripcion: str | None = Field(default=None, max_length=255)
    monto_total: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    fecha_vencimiento: date | None = None


class PagoCrear(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    monto: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    fecha: date | None = Field(default=None, description="Por defecto, hoy (hora de Colombia)")
    nota: str | None = Field(default=None, max_length=255)


class PagoLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    monto: Decimal
    fecha: date
    nota: str | None


class DeudaLeer(BaseModel):
    id: int
    tipo: TipoDeuda
    persona: str
    descripcion: str | None
    monto_total: Decimal
    fecha: date
    fecha_vencimiento: date | None
    creada_en: datetime
    pagado: Decimal
    pendiente: Decimal
    porcentaje: Decimal  # de lo pagado, sobre el total
    saldada: bool
    vencida: bool  # tiene saldo pendiente y ya pasó su fecha de vencimiento


class DeudaDetalle(DeudaLeer):
    pagos: list[PagoLeer]  # los más recientes primero


class ResumenDeudas(BaseModel):
    me_deben: Decimal  # suma de lo pendiente que te deben
    debo: Decimal  # suma de lo pendiente que debes
    neto: Decimal  # me_deben - debo
    cantidad_me_deben: int
    cantidad_debo: int
    vencidas: int
