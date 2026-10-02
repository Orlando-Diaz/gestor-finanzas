from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import TipoDeuda


def _ahora():
    return datetime.now(timezone.utc)


class Deuda(Base):
    """Plata que te deben ("me deben") o que debes ("debo"), con sus abonos.

    Igual que las metas, no mueve el saldo de las cuentas: es un registro para no olvidar quién debe qué.
    """

    __tablename__ = "deudas"
    __table_args__ = (
        CheckConstraint("monto_total > 0", name="ck_deuda_monto_positivo"),
        CheckConstraint("fecha_vencimiento IS NULL OR fecha_vencimiento >= fecha", name="ck_deuda_vencimiento_valido"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[TipoDeuda] = mapped_column(Enum(TipoDeuda))
    persona: Mapped[str] = mapped_column(String(100))
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    monto_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    fecha: Mapped[date] = mapped_column(Date)
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)

    usuario = relationship("Usuario", back_populates="deudas")
    pagos = relationship("PagoDeuda", back_populates="deuda", cascade="all, delete-orphan")


class PagoDeuda(Base):
    __tablename__ = "pagos_deuda"
    __table_args__ = (CheckConstraint("monto > 0", name="ck_pago_monto_positivo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    deuda_id: Mapped[int] = mapped_column(ForeignKey("deudas.id", ondelete="CASCADE"), index=True)
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    fecha: Mapped[date] = mapped_column(Date)
    nota: Mapped[str | None] = mapped_column(String(255), nullable=True)

    deuda = relationship("Deuda", back_populates="pagos")
