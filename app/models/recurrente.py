from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import Frecuencia, TipoTransaccion


class TransaccionRecurrente(Base):
    """Plantilla que genera ingresos o gastos solos (arriendo, salario, Netflix...)."""

    __tablename__ = "transacciones_recurrentes"
    __table_args__ = (
        CheckConstraint("monto > 0", name="ck_recurrente_monto_positivo"),
        CheckConstraint("tipo <> 'TRANSFERENCIA'", name="ck_recurrente_sin_transferencias"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    cuenta_id: Mapped[int] = mapped_column(ForeignKey("cuentas.id"))
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id"))
    tipo: Mapped[TipoTransaccion] = mapped_column(Enum(TipoTransaccion))
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    nota: Mapped[str | None] = mapped_column(String(255), nullable=True)
    frecuencia: Mapped[Frecuencia] = mapped_column(Enum(Frecuencia))
    proxima_fecha: Mapped[date] = mapped_column(Date, index=True)
    # Día del mes con el que empezó (ej. 31): permite volver al 31 después de un febrero
    dia_ancla: Mapped[int] = mapped_column(Integer)
    fecha_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)

    cuenta = relationship("Cuenta")
    categoria = relationship("Categoria")
