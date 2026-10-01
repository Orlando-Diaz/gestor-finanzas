import csv
import io
from typing import Annotated

from fastapi import APIRouter, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DbDep, UsuarioActual
from app.core import tiempo
from app.models import TipoTransaccion, Transaccion
from app.schemas.transaccion import ExportarFiltros
from app.services.consultas import condiciones_transacciones
from app.services.validaciones import error_422

router = APIRouter(prefix="/exportar", tags=["Exportar"])

MAX_FILAS = 50_000
ETIQUETA_TIPO = {
    TipoTransaccion.INGRESO: "Ingreso",
    TipoTransaccion.GASTO: "Gasto",
    TipoTransaccion.TRANSFERENCIA: "Transferencia",
}


def _seguro(texto: str | None) -> str:
    """Evita la inyección de fórmulas: Excel ejecuta las celdas que empiezan por = + - @."""
    if texto and texto[0] in "=+-@\t\r":
        return "'" + texto
    return texto or ""


@router.get("/transacciones", response_class=Response, responses={200: {"content": {"text/csv": {}}}})
def exportar_transacciones(filtros: Annotated[ExportarFiltros, Query()], db: DbDep, usuario: UsuarioActual):
    """Descarga los movimientos (con los mismos filtros del historial) como CSV para Excel, del más antiguo al más reciente."""
    T = Transaccion
    condiciones = condiciones_transacciones(usuario.id, filtros)
    if db.scalar(select(func.count()).select_from(T).where(*condiciones)) > MAX_FILAS:
        raise error_422(f"Son más de {MAX_FILAS} movimientos; acota el rango con 'desde' y 'hasta'")
    filas = db.scalars(
        select(T)
        .options(selectinload(T.cuenta), selectinload(T.cuenta_destino), selectinload(T.categoria))
        .where(*condiciones)
        .order_by(T.fecha, T.id)
    ).all()

    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=filtros.separador, lineterminator="\r\n")
    escritor.writerow(["Fecha", "Tipo", "Monto", "Cuenta", "Cuenta destino", "Categoría", "Nota"])
    for t in filas:
        escritor.writerow([
            t.fecha.isoformat(),
            ETIQUETA_TIPO[t.tipo],
            f"{t.monto:.2f}".replace(".", filtros.decimal),
            _seguro(t.cuenta.nombre),
            _seguro(t.cuenta_destino.nombre) if t.cuenta_destino else "",
            _seguro(t.categoria.nombre) if t.categoria else "",
            _seguro(t.nota),
        ])

    # BOM para que Excel reconozca las tildes (UTF-8)
    contenido = ("﻿" + salida.getvalue()).encode("utf-8")
    nombre = f"transacciones_{tiempo.hoy().isoformat()}.csv"
    return Response(
        content=contenido,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
