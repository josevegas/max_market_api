from __future__ import annotations

from pydantic import BaseModel

from app.shareds.base import RespuestaBase


class BancoCreate(BaseModel):
    razon_social: str
    ruc: str
    direccion: str | None
    telefono: str | None
    codigo: str | None


class BancoUpdate(BaseModel):
    razon_social: str
    ruc: str
    direccion: str | None
    telefono: str | None
    codigo: str | None


class BancoResponse(RespuestaBase):
    razon_social: str
    ruc: str
    direccion: str | None
    telefono: str | None
    codigo: str | None
