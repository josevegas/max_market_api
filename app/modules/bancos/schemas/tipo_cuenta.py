from __future__ import annotations

from pydantic import BaseModel

from app.shared.base import RespuestaBase


class TipoCuentaCreate(BaseModel):
    descripcion: str
    codigo: str


class TipoCuentaUpdate(BaseModel):
    descripcion: str | None
    codigo: str | None


class TipoCuentaResponse(RespuestaBase):
    descripcion: str
    codigo: str
