from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PresupuestoCrear(BaseModel):
    categoria_id: int
    monto_limite: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    mes: int = Field(ge=1, le=12)
    anio: int = Field(ge=2000, le=2100)
    umbral_alerta: int = Field(default=80, ge=1, le=100)


class PresupuestoActualizar(BaseModel):
    monto_limite: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    umbral_alerta: int | None = Field(default=None, ge=1, le=100)


class PresupuestoLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    categoria_id: int
    monto_limite: Decimal
    mes: int
    anio: int
    umbral_alerta: int


class PresupuestoConProgreso(PresupuestoLeer):
    gastado: Decimal
    porcentaje: Decimal
    estado: str  # OK | ALERTA | EXCEDIDO
