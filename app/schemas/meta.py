from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TipoAporte
from app.schemas.categoria import COLOR_HEX


class MetaCrear(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    nombre: str = Field(min_length=1, max_length=80)
    monto_objetivo: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    fecha_objetivo: date | None = None
    icono: str | None = Field(default=None, max_length=40)
    color: str | None = Field(default=None, pattern=COLOR_HEX)


class MetaActualizar(BaseModel):
    """`fecha_objetivo: null` quita la fecha."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    nombre: str | None = Field(default=None, min_length=1, max_length=80)
    monto_objetivo: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    fecha_objetivo: date | None = None
    icono: str | None = Field(default=None, max_length=40)
    color: str | None = Field(default=None, pattern=COLOR_HEX)
    archivada: bool | None = None


class AporteCrear(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    tipo: TipoAporte = TipoAporte.APORTE
    monto: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    fecha: date | None = Field(default=None, description="Por defecto, hoy (hora de Colombia)")
    nota: str | None = Field(default=None, max_length=255)


class AporteLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tipo: TipoAporte
    monto: Decimal
    fecha: date
    nota: str | None


class MetaLeer(BaseModel):
    id: int
    nombre: str
    monto_objetivo: Decimal
    fecha_objetivo: date | None
    icono: str | None
    color: str | None
    archivada: bool
    creada_en: datetime
    ahorrado: Decimal
    faltante: Decimal  # nunca negativo
    porcentaje: Decimal  # puede pasar de 100 si ahorraste de más
    cumplida: bool
    cuota_mensual_sugerida: Decimal | None  # lo que falta repartido en los meses que quedan


class MetaDetalle(MetaLeer):
    aportes: list[AporteLeer]  # los más recientes primero
