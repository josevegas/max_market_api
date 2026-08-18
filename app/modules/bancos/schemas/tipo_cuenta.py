from __future__ import annotations

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase, rechazar_nulos


class TipoCuentaCreate(BaseModel):
    descripcion: str = Field(min_length=1, max_length=50)
    codigo: str = Field(min_length=1, max_length=10)


class TipoCuentaUpdate(BaseModel):
    """Actualización parcial: todo opcional (ver `ZonaUpdate` en markets)."""

    descripcion: str | None = Field(default=None, min_length=1, max_length=50)
    codigo: str | None = Field(default=None, min_length=1, max_length=10)

    # Columnas NOT NULL: omitirlas es válido, mandarlas como null no.
    _no_nulos = rechazar_nulos("descripcion", "codigo")


class TipoCuentaResponse(RespuestaBase):
    descripcion: str
    codigo: str
