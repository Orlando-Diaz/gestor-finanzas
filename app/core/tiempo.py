from datetime import date, datetime, timedelta, timezone

# Colombia no tiene horario de verano: UTC-5 fijo (así no dependemos de tzdata en Windows)
ZONA_COLOMBIA = timezone(timedelta(hours=-5))


def hoy() -> date:
    return datetime.now(ZONA_COLOMBIA).date()


def rango_mes(anio: int, mes: int) -> tuple[date, date]:
    """(primer día del mes, primer día del mes siguiente)."""
    siguiente = date(anio + 1, 1, 1) if mes == 12 else date(anio, mes + 1, 1)
    return date(anio, mes, 1), siguiente


def sumar_meses(anio: int, mes: int, n: int) -> tuple[int, int]:
    indice = anio * 12 + (mes - 1) + n
    return indice // 12, indice % 12 + 1
