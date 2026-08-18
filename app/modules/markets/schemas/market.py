from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase, rechazar_nulos


class MarketCreate(BaseModel):
    sede_id: uuid.UUID
    nombre: str = Field(min_length=1, max_length=50)
    codigo: str = Field(min_length=1, max_length=10)


class MarketUpdate(BaseModel):
    """Actualización parcial: todo opcional (ver `ZonaUpdate`)."""

    sede_id: uuid.UUID | None = None
    nombre: str | None = Field(default=None, min_length=1, max_length=50)
    codigo: str | None = Field(default=None, min_length=1, max_length=10)

    # Columnas NOT NULL: omitirlas es válido, mandarlas como null no.
    _no_nulos = rechazar_nulos("sede_id", "nombre", "codigo")


class MarketResponse(RespuestaBase):
    sede_id: uuid.UUID
    nombre: str
    codigo: str
