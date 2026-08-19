from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase, rechazar_nulos


class PedidoCreate(BaseModel):
    requerimiento_id: uuid.UUID
    #: Opcional: todo documento de la cadena nace pendiente, así que si no
    #: llega el servicio le pone `PEN`. Se admite enviarlo para no cerrarle la
    #: puerta a un alta en otro estado (una carga inicial, por ejemplo), pero
    #: el caso normal no tiene que conocer el id del catálogo.
    estado_id: uuid.UUID | None = None
    fecha: date = Field(default_factory=date.today)


class PedidoUpdate(BaseModel):
    """Actualización parcial: todo opcional."""

    requerimiento_id: uuid.UUID | None = None
    estado_id: uuid.UUID | None = None
    fecha: date | None = None

    _no_nulos = rechazar_nulos("requerimiento_id", "estado_id", "fecha")


class PedidoResponse(RespuestaBase):
    requerimiento_id: uuid.UUID
    estado_id: uuid.UUID
    fecha: date
