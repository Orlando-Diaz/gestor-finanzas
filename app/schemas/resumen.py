from decimal import Decimal

from pydantic import BaseModel


class ResumenMes(BaseModel):
    anio: int
    mes: int
    ingresos: Decimal
    gastos: Decimal
    balance: Decimal  # ingresos - gastos del mes


class TotalPorCategoria(BaseModel):
    categoria_id: int
    categoria: str
    icono: str | None
    color: str | None
    total: Decimal
    porcentaje: Decimal  # sobre el total del mes, para la gráfica de torta


class SerieMensual(BaseModel):
    anio: int
    mes: int
    ingresos: Decimal
    gastos: Decimal
    balance: Decimal


class PuntoBalance(BaseModel):
    """Plata total del usuario (todas sus cuentas) al cierre de un mes."""

    anio: int
    mes: int
    balance: Decimal
