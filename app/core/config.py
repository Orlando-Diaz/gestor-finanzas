from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SECRET_POR_DEFECTO = "dev-only-cambia-esto-no-usar-en-produccion"


def normalizar_url_base_de_datos(url: str) -> str:
    """Los proveedores (Render, Neon, Heroku...) entregan `postgres://` o `postgresql://`,
    pero SQLAlchemy necesita indicar el driver: `postgresql+psycopg2://`."""
    for prefijo in ("postgres://", "postgresql://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg2://" + url[len(prefijo):]
    return url


class Settings(BaseSettings):
    database_url: str = "sqlite:///./mis_finanzas.db"
    secret_key: str = SECRET_POR_DEFECTO
    access_token_expire_minutes: int = 60
    moneda_por_defecto: str = "COP"
    entorno: str = "desarrollo"
    bcrypt_rounds: int = 12  # las pruebas lo bajan para ir rápido; en producción debe ser >= 10

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def completar_url_de_la_base(self):
        self.database_url = normalizar_url_base_de_datos(self.database_url.strip())
        return self

    @model_validator(mode="after")
    def exigir_secreto_seguro_en_produccion(self):
        if self.entorno == "produccion" and (
            self.secret_key in (SECRET_POR_DEFECTO, "cambia-esto") or len(self.secret_key) < 32
        ):
            raise ValueError("En produccion SECRET_KEY debe ser un valor aleatorio de al menos 32 caracteres")
        if self.entorno == "produccion" and self.bcrypt_rounds < 10:
            raise ValueError("En produccion BCRYPT_ROUNDS debe ser al menos 10")
        return self


settings = Settings()
