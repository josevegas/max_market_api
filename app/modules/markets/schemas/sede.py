from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase, rechazar_nulos


class SedeCreate(BaseModel):
    zona_id: uuid.UUID
    nombre: str = Field(min_length=1, max_length=50)
    codigo: str = Field(min_length=1, max_length=10)


class SedeUpdate(BaseModel):
    """Actualización parcial: todo opcional (ver `ZonaUpdate`)."""

    zona_id: uuid.UUID | None = None
    nombre: str | None = Field(default=None, min_length=1, max_length=50)
    codigo: str | None = Field(default=None, min_length=1, max_length=10)

    # Columnas NOT NULL: omitirlas es válido, mandarlas como null no.
    _no_nulos = rechazar_nulos("zona_id", "nombre", "codigo")


class SedeResponse(RespuestaBase):
    zona_id: uuid.UUID
    nombre: str
    codigo: str
