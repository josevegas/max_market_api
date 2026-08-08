from __future__ import annotations

from pydantic import BaseModel

from app.shared.base import RespuestaBase


class ZonaCreate(BaseModel):
    nombre: str
    codigo: str


class ZonaUpdate(BaseModel):
    nombre: str | None
    codigo: str | None


class ZonaResponse(RespuestaBase):
    nombre: str
    codigo: str
