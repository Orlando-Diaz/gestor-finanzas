import pytest

from app.core.config import Settings, normalizar_url_base_de_datos


@pytest.mark.parametrize(
    "entrada, esperada",
    [
        ("postgres://u:p@host:5432/db", "postgresql+psycopg2://u:p@host:5432/db"),
        ("postgresql://u:p@host/db?sslmode=require", "postgresql+psycopg2://u:p@host/db?sslmode=require"),
        ("postgresql+psycopg2://u:p@host/db", "postgresql+psycopg2://u:p@host/db"),
        ("sqlite:///./mis_finanzas.db", "sqlite:///./mis_finanzas.db"),
    ],
)
def test_normaliza_la_url_de_la_base(entrada, esperada):
    assert normalizar_url_base_de_datos(entrada) == esperada


def test_settings_aplica_la_normalizacion_y_limpia_espacios():
    s = Settings(_env_file=None, database_url="  postgres://u:p@h/db\n")
    assert s.database_url == "postgresql+psycopg2://u:p@h/db"


def test_produccion_exige_secreto_seguro():
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(_env_file=None, entorno="produccion", secret_key="corto")
    Settings(_env_file=None, entorno="produccion", secret_key="x" * 40, bcrypt_rounds=12)
