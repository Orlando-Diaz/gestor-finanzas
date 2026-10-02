from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import TipoAporte


def _ahora():
    return datetime.now(timezone.utc)


class Meta(Base):
    """Meta de ahorro (viaje, moto, fondo de emergencia...).

    Lo ahorrado se calcula con los aportes y retiros; no mueve el saldo de ninguna cuenta:
    es plata que ya tienes y decides "apartar" mentalmente para un objetivo.
    """

    __tablename__ = "metas"
    __table_args__ = (CheckConstraint("monto_objetivo > 0", name="ck_meta_objetivo_positivo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    nombre: Mapped[str] = mapped_column(String(80))
    monto_objetivo: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    fecha_objetivo: Mapped[date | None] = mapped_column(Date, nullable=True)
    icono: Mapped[str | None] = mapped_column(String(40), nullable=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    archivada: Mapped[bool] = mapped_column(Boolean, default=False)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)

    usuario = relationship("Usuario", back_populates="metas")
    aportes = relationship("AporteMeta", back_populates="meta", cascade="all, delete-orphan")


class AporteMeta(Base):
    __tablename__ = "aportes_meta"
    __table_args__ = (CheckConstraint("monto > 0", name="ck_aporte_monto_positivo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    meta_id: Mapped[int] = mapped_column(ForeignKey("metas.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[TipoAporte] = mapped_column(Enum(TipoAporte))
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    fecha: Mapped[date] = mapped_column(Date)
    nota: Mapped[str | None] = mapped_column(String(255), nullable=True)

    meta = relationship("Meta", back_populates="aportes")
