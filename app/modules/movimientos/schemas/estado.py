from __future__ import annotations

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase, rechazar_nulos


class EstadoCreate(BaseModel):
    descripcion: str = Field(min_length=1, max_length=30)
    codigo: str = Field(min_length=1, max_length=10)


class EstadoUpdate(BaseModel):
    """Actualización parcial: todo opcional."""

    descripcion: str | None = Field(default=None, min_length=1, max_length=30)
    codigo: str | None = Field(default=None, min_length=1, max_length=10)

    _no_nulos = rechazar_nulos("descripcion", "codigo")


class EstadoResponse(RespuestaBase):
    descripcion: str
    codigo: str
