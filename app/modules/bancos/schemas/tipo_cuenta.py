from __future__ import annotations

from pydantic import BaseModel

from app.shareds.base import RespuestaBase


class TipoCuentaCreate(BaseModel):
    descripcion: str
    codigo: str


class TipoCuentaUpdate(BaseModel):
    descripcion: str
    codigo: str


class TipoCuentaResponse(RespuestaBase):
    descripcion: str
    codigo: str
