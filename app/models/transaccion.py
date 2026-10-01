from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import TipoTransaccion


def _ahora():
    return datetime.now(timezone.utc)


class Transaccion(Base):
    """Ingreso, gasto o transferencia entre cuentas propias.

    - El monto siempre es positivo; el signo lo da el tipo.
    - Una transferencia es UNA fila (cuenta_id = origen, cuenta_destino_id = destino)
      y no cuenta como ingreso ni gasto en las gráficas.
    """

    __tablename__ = "transacciones"
    __table_args__ = (
        CheckConstraint("monto > 0", name="ck_transaccion_monto_positivo"),
        CheckConstraint(
            "(tipo = 'TRANSFERENCIA' AND cuenta_destino_id IS NOT NULL "
            "AND cuenta_destino_id <> cuenta_id) "
            "OR (tipo <> 'TRANSFERENCIA' AND cuenta_destino_id IS NULL)",
            name="ck_transaccion_transferencia_valida",
        ),
        Index("ix_transaccion_usuario_fecha", "usuario_id", "fecha"),
        Index("ix_transaccion_usuario_categoria", "usuario_id", "categoria_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    cuenta_id: Mapped[int] = mapped_column(ForeignKey("cuentas.id"))
    cuenta_destino_id: Mapped[int | None] = mapped_column(ForeignKey("cuentas.id"), nullable=True)
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("categorias.id"), nullable=True)
    recurrente_id: Mapped[int | None] = mapped_column(
        ForeignKey("transacciones_recurrentes.id", ondelete="SET NULL"), nullable=True
    )
    tipo: Mapped[TipoTransaccion] = mapped_column(Enum(TipoTransaccion))
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    fecha: Mapped[date] = mapped_column(Date)
    nota: Mapped[str | None] = mapped_column(String(255), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora, onupdate=_ahora)

    usuario = relationship("Usuario", back_populates="transacciones")
    cuenta = relationship("Cuenta", foreign_keys=[cuenta_id])
    cuenta_destino = relationship("Cuenta", foreign_keys=[cuenta_destino_id])
    categoria = relationship("Categoria")
