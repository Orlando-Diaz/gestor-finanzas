from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UsuarioCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def maximo_72_bytes(cls, v: str) -> str:
        # bcrypt solo admite 72 bytes (un carácter con tilde pesa 2)
        if len(v.encode("utf-8")) > 72:
            raise ValueError("La contraseña es demasiado larga (máximo 72 bytes)")
        return v


class UsuarioLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    email: EmailStr
    moneda_por_defecto: str
    creado_en: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
