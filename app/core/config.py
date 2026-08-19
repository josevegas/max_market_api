"""Configuración de la aplicación, leída del entorno (.env)."""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Base de datos ───────────────────────────────────────────────────────
    DATABASE_URL: str

    # ── API externa de consulta de RUC (decolecta) ──────────────────────────
    #: URL **base**, sin query string: el número se manda como parámetro
    #: (`?numero=...`), no concatenado. Se aceptan los nombres antiguos
    #: (`URL_API`, `API_JSON_TOKEN`) para no romper los `.env` que ya existen.
    URL_API_RUC: str = Field(
        default="https://api.decolecta.com/v1/sunat/ruc",
        validation_alias=AliasChoices("URL_API_RUC", "URL_API"),
    )
    API_RUC_TOKEN: str = Field(
        default="",
        validation_alias=AliasChoices("API_RUC_TOKEN", "API_JSON_TOKEN"),
    )

    @field_validator("URL_API_RUC")
    @classmethod
    def _url_base(cls, v: str) -> str:
        """Descarta la query string que llevaba la forma anterior.

        Antes la URL terminaba en `?numero=` porque el RUC se pegaba a mano.
        Ahora va como parámetro, así que un `.env` sin actualizar seguiría
        funcionando en vez de pedir `...ruc?numero=?numero=20552103816`.
        """
        return v.split("?")[0].rstrip("/")

    # ── Padrones de agentes de retención/percepción (SUNAT) ─────────────────
    #: ZIP con un TXT separado por "|". Son públicos y no piden token, por eso
    #: llevan valor por defecto: sin `.env` la sincronización igual funciona.
    URL_PADRON_RETENCION: str = (
        "https://ww1.sunat.gob.pe/descarga/AgentRet/AgenRet_TXT.zip"
    )
    URL_PADRON_PERCEPCION: str = (
        "https://ww1.sunat.gob.pe/descarga/AgentRet/AgenPercVI_TXT.zip"
    )

    # ── Precios ─────────────────────────────────────────────────────────────
    #: IGV vigente, **como factor**: 18% se escribe 1.18. Va acá y no como
    #: constante en el código porque la tasa cambia por ley, y el día que
    #: cambie no se puede depender de un despliegue para corregir los precios.
    IGV: Decimal = Decimal("1.18")
    #: Recargo fijo por operación en punto de venta. Entra al precio antes del
    #: IGV, así que también tributa. Cero por defecto: es una decisión
    #: comercial de cada instalación, no un supuesto que la API pueda hacer.
    MONTO_POS: Decimal = Decimal("0")

    # ── Aplicación ──────────────────────────────────────────────────────────
    APP_NAME: str = "Max Market API"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    #: Orígenes que pueden llamar a la API desde el navegador, separados por
    #: coma. El navegador bloquea cualquier otro: en producción hay que poner
    #: el dominio real, nunca "*" si se envían credenciales.
    CORS_ORIGINS: str = "http://localhost:4300,http://127.0.0.1:4300"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

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
