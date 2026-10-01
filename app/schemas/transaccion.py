from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import TipoTransaccion


class TransaccionCrear(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    tipo: TipoTransaccion
    monto: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    fecha: date
    cuenta_id: int
    cuenta_destino_id: int | None = None  # solo TRANSFERENCIA
    categoria_id: int | None = None  # no aplica a TRANSFERENCIA
    nota: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validar_segun_tipo(self):
        if self.tipo == TipoTransaccion.TRANSFERENCIA:
            if self.cuenta_destino_id is None:
                raise ValueError("Una transferencia necesita cuenta_destino_id")
            if self.cuenta_destino_id == self.cuenta_id:
                raise ValueError("La cuenta de origen y destino deben ser distintas")
            if self.categoria_id is not None:
                raise ValueError("Una transferencia no lleva categoría")
        else:
            if self.cuenta_destino_id is not None:
                raise ValueError("Solo las transferencias llevan cuenta_destino_id")
            if self.categoria_id is None:
                raise ValueError("Un ingreso o gasto necesita categoria_id")
        return self


class TransaccionActualizar(BaseModel):
    """El tipo no se puede cambiar: para eso se borra y se crea de nuevo."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    monto: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    fecha: date | None = None
    cuenta_id: int | None = None
    cuenta_destino_id: int | None = None  # solo transferencias
    categoria_id: int | None = None  # no aplica a transferencias
    nota: str | None = Field(default=None, max_length=255)


class CuentaResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str


class CategoriaResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    icono: str | None
    color: str | None


class TransaccionLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: TipoTransaccion
    monto: Decimal
    fecha: date
    nota: str | None
    cuenta: CuentaResumen
    cuenta_destino: CuentaResumen | None
    categoria: CategoriaResumen | None
    creado_en: datetime


class PaginaTransacciones(BaseModel):
    items: list[TransaccionLeer]
    total: int
    pagina: int
    por_pagina: int


class TransaccionFiltros(BaseModel):
    """Parámetros de consulta para el historial."""

    desde: date | None = None
    hasta: date | None = None
    tipo: TipoTransaccion | None = None
    cuenta_id: int | None = None
    categoria_id: int | None = None
    pagina: int = Field(default=1, ge=1)
    por_pagina: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def rango_valido(self):
        if self.desde and self.hasta and self.desde > self.hasta:
            raise ValueError("'desde' no puede ser posterior a 'hasta'")
        return self
