from decimal import Decimal

from pydantic import BaseModel


class ResumenMes(BaseModel):
    anio: int
    mes: int
    ingresos: Decimal
    gastos: Decimal
    balance: Decimal


class GastoPorCategoria(BaseModel):
    categoria_id: int
    categoria: str
    color: str | None
    total: Decimal


class SerieMensual(BaseModel):
    anio: int
    mes: int
    ingresos: Decimal
    gastos: Decimal
