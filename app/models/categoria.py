from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import TipoCategoria


class Categoria(Base):
    """usuario_id nulo = categoría predeterminada, visible para todos."""

    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True, nullable=True
    )
    nombre: Mapped[str] = mapped_column(String(60))
    tipo: Mapped[TipoCategoria] = mapped_column(Enum(TipoCategoria))
    icono: Mapped[str | None] = mapped_column(String(40), nullable=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)  # #RRGGBB
    categoria_padre_id: Mapped[int | None] = mapped_column(
        ForeignKey("categorias.id", ondelete="SET NULL"), nullable=True
    )
    archivada: Mapped[bool] = mapped_column(Boolean, default=False)

    @property
    def predeterminada(self) -> bool:
        return self.usuario_id is None

    usuario = relationship("Usuario", back_populates="categorias")
    subcategorias = relationship("Categoria", backref="padre", remote_side=[id])
