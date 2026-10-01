from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.transaccion import CategoriaResumen


class PresupuestoCrear(BaseModel):
    categoria_id: int
    monto_limite: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    mes: int = Field(ge=1, le=12)
    anio: int = Field(ge=2000, le=2100)
    umbral_alerta: int = Field(default=80, ge=1, le=100, description="% del límite en el que se avisa")


class PresupuestoActualizar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monto_limite: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    umbral_alerta: int | None = Field(default=None, ge=1, le=100)


class PresupuestoLeer(BaseModel):
    id: int
    categoria: CategoriaResumen
    mes: int
    anio: int
    monto_limite: Decimal
    umbral_alerta: int
    gastado: Decimal
    restante: Decimal  # negativo si se excedió
    porcentaje: Decimal
    estado: Literal["OK", "ALERTA", "EXCEDIDO"]


class CopiarPresupuestos(BaseModel):
    desde_anio: int = Field(ge=2000, le=2100)
    desde_mes: int = Field(ge=1, le=12)
    a_anio: int = Field(ge=2000, le=2100)
    a_mes: int = Field(ge=1, le=12)

    @model_validator(mode="after")
    def periodos_distintos(self):
        if (self.desde_anio, self.desde_mes) == (self.a_anio, self.a_mes):
            raise ValueError("El mes de origen y el de destino deben ser distintos")
        return self
