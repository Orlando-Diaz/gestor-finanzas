from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import Frecuencia, TipoTransaccion


class TransaccionRecurrente(Base):
    """Plantilla que genera transacciones solas (arriendo, salario, Netflix...)."""

    __tablename__ = "transacciones_recurrentes"
    __table_args__ = (CheckConstraint("monto > 0", name="ck_recurrente_monto_positivo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    cuenta_id: Mapped[int] = mapped_column(ForeignKey("cuentas.id"))
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("categorias.id"), nullable=True)
    tipo: Mapped[TipoTransaccion] = mapped_column(Enum(TipoTransaccion))
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    nota: Mapped[str | None] = mapped_column(String(255), nullable=True)
    frecuencia: Mapped[Frecuencia] = mapped_column(Enum(Frecuencia))
    proxima_fecha: Mapped[date] = mapped_column(Date, index=True)
    fecha_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
