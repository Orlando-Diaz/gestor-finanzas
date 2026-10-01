from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import TipoCuenta


class Cuenta(Base):
    """De dónde sale o a dónde entra la plata: Efectivo, Nequi, Bancolombia...

    El saldo actual NO se guarda: se calcula a partir de saldo_inicial y las
    transacciones, así nunca puede quedar desincronizado.
    """

    __tablename__ = "cuentas"
    __table_args__ = (UniqueConstraint("usuario_id", "nombre", name="uq_cuenta_usuario_nombre"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    nombre: Mapped[str] = mapped_column(String(60))
    tipo: Mapped[TipoCuenta] = mapped_column(Enum(TipoCuenta))
    saldo_inicial: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    archivada: Mapped[bool] = mapped_column(Boolean, default=False)

    usuario = relationship("Usuario", back_populates="cuentas")
