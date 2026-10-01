from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SECRET_POR_DEFECTO = "dev-only-cambia-esto-no-usar-en-produccion"


class Settings(BaseSettings):
    database_url: str = "sqlite:///./mis_finanzas.db"
    secret_key: str = SECRET_POR_DEFECTO
    access_token_expire_minutes: int = 60
    moneda_por_defecto: str = "COP"
    entorno: str = "desarrollo"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def exigir_secreto_seguro_en_produccion(self):
        if self.entorno == "produccion" and (
            self.secret_key in (SECRET_POR_DEFECTO, "cambia-esto") or len(self.secret_key) < 32
        ):
            raise ValueError("En produccion SECRET_KEY debe ser un valor aleatorio de al menos 32 caracteres")
        return self


settings = Settings()
