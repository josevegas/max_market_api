from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.shared.base import RespuestaBase


class SedeCreate(BaseModel):
    zona_id: uuid.UUID
    nombre: str
    codigo: str


class SedeUpdate(BaseModel):
    zona_id: uuid.UUID | None
    nombre: str | None
    codigo: str | None


class SedeResponse(RespuestaBase):
    zona_id: uuid.UUID
    nombre: str
    codigo: str
