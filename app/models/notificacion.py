from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import TipoNotificacion


def _ahora():
    return datetime.now(timezone.utc)


class Notificacion(Base):
    __tablename__ = "notificaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[TipoNotificacion] = mapped_column(Enum(TipoNotificacion))
    mensaje: Mapped[str] = mapped_column(String(255))
    # Presupuesto que la originó (sirve para no repetir la misma alerta); si el presupuesto se borra, queda nulo
    presupuesto_id: Mapped[int | None] = mapped_column(
        ForeignKey("presupuestos.id", ondelete="SET NULL"), nullable=True, index=True
    )
    leida: Mapped[bool] = mapped_column(Boolean, default=False)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)

    usuario = relationship("Usuario", back_populates="notificaciones")
