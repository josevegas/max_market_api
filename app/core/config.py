"""Configuración de la aplicación, leída del entorno (.env)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Base de datos ───────────────────────────────────────────────────────
    DATABASE_URL: str

    # ── API externa (api.json.pe: consultas RUC/DNI) ────────────────────────
    URL_API: str = ""
    API_JSON_TOKEN: str = ""

    # ── Aplicación ──────────────────────────────────────────────────────────
    APP_NAME: str = "Max Market API"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    @property
    def database_url_sync(self) -> str:
        """La misma URL con driver síncrono.

        Alembic y algunas herramientas no hablan asyncpg; se deriva de la
        única URL configurada para que no haya dos fuentes de verdad.
        """
        return self.DATABASE_URL.replace("+asyncpg", "").replace(
            "postgresql://", "postgresql+psycopg2://"
        )


@lru_cache
def get_settings() -> Settings:
    """Settings cacheada: se lee el entorno una sola vez por proceso."""
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
