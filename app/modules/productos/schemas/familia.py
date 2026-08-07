from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.productos.schemas.base import RespuestaBase


class FamiliaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    codigo: str | None = Field(default=None, max_length=10)


class FamiliaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    codigo: str | None = Field(default=None, max_length=10)


class FamiliaResponse(RespuestaBase):
    nombre: str
    codigo: str | None = None
