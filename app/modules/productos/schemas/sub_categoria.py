from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.shareds.base import RespuestaBase


class SubCategoriaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    codigo: str | None = Field(default=None, max_length=10)
    categoria_id: uuid.UUID


class SubCategoriaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    codigo: str | None = Field(default=None, max_length=10)
    categoria_id: uuid.UUID | None = None


class SubCategoriaResponse(RespuestaBase):
    nombre: str
    codigo: str | None = None
    categoria_id: uuid.UUID
