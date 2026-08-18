from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase, rechazar_nulos


class GuiaRemisionCreate(BaseModel):
    # La columna es `orden_compra_id`; antes el schema y el modelo usaban
    # nombres distintos y no se podía crear ninguna guía.
    orden_compra_id: uuid.UUID
    #: Es NOT NULL en la tabla y faltaba acá: el INSERT moría por integridad.
    estado_id: uuid.UUID
    fecha: date = Field(default_factory=date.today)


class GuiaRemisionUpdate(BaseModel):
    """Actualización parcial: todo opcional."""

    orden_compra_id: uuid.UUID | None = None
    estado_id: uuid.UUID | None = None
    fecha: date | None = None

    _no_nulos = rechazar_nulos("orden_compra_id", "estado_id", "fecha")


class GuiaRemisionResponse(RespuestaBase):
    orden_compra_id: uuid.UUID
    estado_id: uuid.UUID
    fecha: date
