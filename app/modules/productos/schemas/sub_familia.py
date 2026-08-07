from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.modules.productos.schemas.base import RespuestaBase


class SubFamiliaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    codigo: str | None = Field(default=None, max_length=10)
    familia_id: uuid.UUID


class SubFamiliaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    codigo: str | None = Field(default=None, max_length=10)
    familia_id: uuid.UUID | None = None


class SubFamiliaResponse(RespuestaBase):
    nombre: str
    codigo: str | None = None
    familia_id: uuid.UUID
