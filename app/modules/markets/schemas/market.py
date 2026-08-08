from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.shared.base import RespuestaBase


class MarketCreate(BaseModel):
    sede_id: uuid.UUID
    nombre: str
    codigo: str


class MarketUpdate(BaseModel):
    sede_id: uuid.UUID | None
    nombre: str | None
    codigo: str | None


class MarketResponse(RespuestaBase):
    sede_id: uuid.UUID
    nombre: str
    codigo: str
