from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase, rechazar_nulos


class CotizacionCreate(BaseModel):
    pedido_id: uuid.UUID
    proveedor_id: uuid.UUID
    estado_id: uuid.UUID
    #: Días que el proveedor tarda en atender, como en `proveedor_productos`.
    tiempo_atencion: int = Field(default=0, ge=0, le=365)
    fecha: date = Field(default_factory=date.today)
    # `monto_total` no se envía: lo recalcula el servicio sumando las líneas.


class CotizacionUpdate(BaseModel):
    """Actualización parcial: todo opcional."""

    pedido_id: uuid.UUID | None = None
    proveedor_id: uuid.UUID | None = None
    # El nombre es `estado_id`, como la columna: antes decía `estado` y ni el
    # PATCH ni la respuesta funcionaban.
    estado_id: uuid.UUID | None = None
    tiempo_atencion: int | None = Field(default=None, ge=0, le=365)
    fecha: date | None = None

    _no_nulos = rechazar_nulos(
        "pedido_id", "proveedor_id", "estado_id", "tiempo_atencion", "fecha"
    )


class CotizacionResponse(RespuestaBase):
    pedido_id: uuid.UUID
    proveedor_id: uuid.UUID
    estado_id: uuid.UUID
    tiempo_atencion: int
    fecha: date
    monto_total: Decimal
