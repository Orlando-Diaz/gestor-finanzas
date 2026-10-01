import logging

from sqlalchemy.orm import Session

from app.services.categorias_default import sembrar_categorias_default
from app.services.recurrentes import procesar_recurrentes

log = logging.getLogger(__name__)


def tareas_de_arranque(db: Session) -> None:
    """Se ejecuta cada vez que arranca la app (después de preparar las tablas).

    - Crea las categorías predeterminadas que falten.
    - Registra los movimientos recurrentes que vencieron mientras la app estaba apagada
      (en hosting gratuito la app se duerme, así que esto es lo normal y no la excepción).
    """
    sembrar_categorias_default(db)
    try:
        generadas = procesar_recurrentes(db)
        if generadas:
            log.info("Recurrentes: %s movimientos registrados al arrancar", generadas)
    except Exception:  # un fallo aquí no debe impedir que la app arranque
        db.rollback()
        log.exception("No se pudieron procesar las recurrentes al arrancar")
