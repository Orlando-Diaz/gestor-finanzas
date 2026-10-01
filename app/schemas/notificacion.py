from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import TipoNotificacion


class NotificacionLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: TipoNotificacion
    mensaje: str
    presupuesto_id: int | None
    leida: bool
    creada_en: datetime


class ConteoNotificaciones(BaseModel):
    no_leidas: int
