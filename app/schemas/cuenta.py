from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TipoCuenta


class CuentaCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)
    tipo: TipoCuenta
    saldo_inicial: Decimal = Field(default=Decimal("0"), max_digits=14, decimal_places=2)


class CuentaActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=60)
    tipo: TipoCuenta | None = None
    archivada: bool | None = None


class CuentaLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    tipo: TipoCuenta
    saldo_inicial: Decimal
    archivada: bool


class CuentaConSaldo(CuentaLeer):
    saldo_actual: Decimal
