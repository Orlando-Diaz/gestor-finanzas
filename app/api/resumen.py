from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import case, extract, func, select
from sqlalchemy.orm import aliased

from app.api.deps import AnioQ, DbDep, MesQ, UsuarioActual, periodo_o_actual
from app.core.tiempo import rango_mes, sumar_meses
from app.models import Categoria, Cuenta, TipoCategoria, TipoTransaccion, Transaccion
from app.schemas.resumen import PuntoBalance, ResumenMes, SerieMensual, TotalPorCategoria
from app.services.saldos import CENTAVOS

router = APIRouter(prefix="/resumen", tags=["Resumen"])

T = Transaccion


def _dinero(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(CENTAVOS)


def _ingresos_gastos():
    """Sumas condicionales; las transferencias se excluyen en el WHERE."""
    ingresos = func.coalesce(func.sum(case((T.tipo == TipoTransaccion.INGRESO, T.monto), else_=0)), 0)
    gastos = func.coalesce(func.sum(case((T.tipo == TipoTransaccion.GASTO, T.monto), else_=0)), 0)
    return ingresos, gastos


def _serie(db, usuario_id: int, anio_fin: int, mes_fin: int, meses: int) -> list[SerieMensual]:
    anio_ini, mes_ini = sumar_meses(anio_fin, mes_fin, -(meses - 1))
    inicio, _ = rango_mes(anio_ini, mes_ini)
    _, fin = rango_mes(anio_fin, mes_fin)
    ingresos, gastos = _ingresos_gastos()
    filas = db.execute(
        select(extract("year", T.fecha), extract("month", T.fecha), ingresos, gastos)
        .where(
            T.usuario_id == usuario_id,
            T.tipo != TipoTransaccion.TRANSFERENCIA,
            T.fecha >= inicio,
            T.fecha < fin,
        )
        .group_by(extract("year", T.fecha), extract("month", T.fecha))
    ).all()
    por_mes = {(int(a), int(m)): (_dinero(i), _dinero(g)) for a, m, i, g in filas}

    serie = []
    for k in range(meses):
        anio, mes = sumar_meses(anio_ini, mes_ini, k)
        ing, gas = por_mes.get((anio, mes), (Decimal("0.00"), Decimal("0.00")))
        serie.append(SerieMensual(anio=anio, mes=mes, ingresos=ing, gastos=gas, balance=ing - gas))
    return serie


@router.get("/mes", response_model=ResumenMes)
def resumen_mes(db: DbDep, usuario: UsuarioActual, anio: AnioQ = None, mes: MesQ = None):
    """Ingresos, gastos y balance de un mes (por defecto, el actual)."""
    anio, mes = periodo_o_actual(anio, mes)
    punto = _serie(db, usuario.id, anio, mes, 1)[0]
    return ResumenMes(anio=anio, mes=mes, ingresos=punto.ingresos, gastos=punto.gastos, balance=punto.balance)


@router.get("/por-categoria", response_model=list[TotalPorCategoria])
def por_categoria(
    db: DbDep,
    usuario: UsuarioActual,
    anio: AnioQ = None,
    mes: MesQ = None,
    tipo: TipoCategoria = TipoCategoria.GASTO,
    agrupar_subcategorias: bool = True,
):
    """Total por categoría en un mes, de mayor a menor (gráfica de torta).

    Con `agrupar_subcategorias` (por defecto) lo de una subcategoría se suma a su categoría padre.
    """
    anio, mes = periodo_o_actual(anio, mes)
    inicio, fin = rango_mes(anio, mes)
    C, P = aliased(Categoria), aliased(Categoria)
    clave = P if agrupar_subcategorias else C
    total = func.sum(T.monto)

    consulta = select(clave.id, clave.nombre, clave.icono, clave.color, total).select_from(T).join(C, C.id == T.categoria_id)
    if agrupar_subcategorias:
        consulta = consulta.join(P, P.id == func.coalesce(C.categoria_padre_id, C.id))
    filas = db.execute(
        consulta.where(
            T.usuario_id == usuario.id,
            T.tipo == TipoTransaccion(tipo.value),
            T.fecha >= inicio,
            T.fecha < fin,
        )
        .group_by(clave.id, clave.nombre, clave.icono, clave.color)
        .order_by(total.desc(), clave.nombre)
    ).all()

    suma = sum((_dinero(f[4]) for f in filas), Decimal(0))
    return [
        TotalPorCategoria(
            categoria_id=cid,
            categoria=nombre,
            icono=icono,
            color=color,
            total=_dinero(t),
            porcentaje=(_dinero(t) * 100 / suma).quantize(CENTAVOS),
        )
        for cid, nombre, icono, color, t in filas
    ]


@router.get("/serie-mensual", response_model=list[SerieMensual])
def serie_mensual(
    db: DbDep,
    usuario: UsuarioActual,
    meses: Annotated[int, Query(ge=1, le=24)] = 6,
    anio: AnioQ = None,
    mes: MesQ = None,
):
    """Ingresos contra gastos de los últimos `meses` meses, hasta el mes indicado (gráfica de barras).

    Siempre devuelve todos los meses del rango, en orden, con ceros donde no hubo movimientos.
    """
    anio, mes = periodo_o_actual(anio, mes)
    return _serie(db, usuario.id, anio, mes, meses)


@router.get("/evolucion-balance", response_model=list[PuntoBalance])
def evolucion_balance(
    db: DbDep,
    usuario: UsuarioActual,
    meses: Annotated[int, Query(ge=1, le=24)] = 6,
    anio: AnioQ = None,
    mes: MesQ = None,
):
    """Plata total (suma de todas las cuentas) al cierre de cada mes (gráfica de línea).

    Parte de la suma de los saldos iniciales y acumula ingresos - gastos. Las transferencias
    entre cuentas propias no cambian el total. El saldo inicial de cada cuenta cuenta desde el
    primer mes del rango, porque las cuentas no guardan fecha de apertura.
    """
    anio, mes = periodo_o_actual(anio, mes)
    serie = _serie(db, usuario.id, anio, mes, meses)
    inicio, _ = rango_mes(serie[0].anio, serie[0].mes)

    base = db.scalar(select(func.coalesce(func.sum(Cuenta.saldo_inicial), 0)).where(Cuenta.usuario_id == usuario.id))
    previo = db.scalar(
        select(func.coalesce(func.sum(case((T.tipo == TipoTransaccion.INGRESO, T.monto), else_=-T.monto)), 0)).where(
            T.usuario_id == usuario.id, T.tipo != TipoTransaccion.TRANSFERENCIA, T.fecha < inicio
        )
    )
    acumulado = _dinero(base) + _dinero(previo)
    puntos = []
    for p in serie:
        acumulado += p.balance
        puntos.append(PuntoBalance(anio=p.anio, mes=p.mes, balance=acumulado))
    return puntos
