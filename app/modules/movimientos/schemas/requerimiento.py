from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase, rechazar_nulos


class RequerimientoCreate(BaseModel):
    almacen_id: uuid.UUID
    estado_id: uuid.UUID
    fecha: date = Field(default_factory=date.today)


class RequerimientoUpdate(BaseModel):
    """Actualización parcial: todo opcional."""

    almacen_id: uuid.UUID | None = None
    estado_id: uuid.UUID | None = None
    fecha: date | None = None

    _no_nulos = rechazar_nulos("almacen_id", "estado_id", "fecha")


class RequerimientoResponse(RespuestaBase):
    almacen_id: uuid.UUID
    estado_id: uuid.UUID
    fecha: date
