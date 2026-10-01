from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./mis_finanzas.db"
    secret_key: str = "dev-only-cambia-esto"
    access_token_expire_minutes: int = 60
    moneda_por_defecto: str = "COP"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
