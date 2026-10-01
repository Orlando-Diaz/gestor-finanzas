from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TipoCategoria

COLOR_HEX = r"^#[0-9A-Fa-f]{6}$"


class CategoriaCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)
    tipo: TipoCategoria
    icono: str | None = Field(default=None, max_length=40)
    color: str | None = Field(default=None, pattern=COLOR_HEX)
    categoria_padre_id: int | None = None


class CategoriaActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=60)
    icono: str | None = Field(default=None, max_length=40)
    color: str | None = Field(default=None, pattern=COLOR_HEX)
    archivada: bool | None = None


class CategoriaLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    tipo: TipoCategoria
    icono: str | None
    color: str | None
    categoria_padre_id: int | None
    archivada: bool
    predeterminada: bool = False
