from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Presupuesto(Base):
    """Límite mensual de gasto para una categoría."""

    __tablename__ = "presupuestos"
    __table_args__ = (
        UniqueConstraint("usuario_id", "categoria_id", "anio", "mes", name="uq_presupuesto_periodo"),
        CheckConstraint("monto_limite > 0", name="ck_presupuesto_limite_positivo"),
        CheckConstraint("mes BETWEEN 1 AND 12", name="ck_presupuesto_mes"),
        CheckConstraint("umbral_alerta BETWEEN 1 AND 100", name="ck_presupuesto_umbral"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id"))
    monto_limite: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    mes: Mapped[int] = mapped_column(Integer)
    anio: Mapped[int] = mapped_column(Integer)
    umbral_alerta: Mapped[int] = mapped_column(Integer, default=80)  # % del límite

    usuario = relationship("Usuario", back_populates="presupuestos")
    categoria = relationship("Categoria")
