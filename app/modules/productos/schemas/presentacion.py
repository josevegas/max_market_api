from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.productos.schemas.base import RespuestaBase


class PresentacionCreate(BaseModel):
    descripcion: str = Field(min_length=1, max_length=150)
    codigo: str | None = Field(default=None, max_length=10)


class PresentacionUpdate(BaseModel):
    descripcion: str | None = Field(default=None, min_length=1, max_length=150)
    codigo: str | None = Field(default=None, max_length=10)


class PresentacionResponse(RespuestaBase):
    descripcion: str
    codigo: str | None = None
