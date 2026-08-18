from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase, rechazar_nulos


class OrdenCompraCreate(BaseModel):
    cotizacion_id: uuid.UUID
    # `estado_id` y no `estado: str`: la columna es una FK a `estados`, así que
    # un texto libre acababa en "invalid keyword argument" al crear.
    estado_id: uuid.UUID
    fecha: date = Field(default_factory=date.today)
    # Ni `proveedor_id` (se obtiene de la cotización) ni `monto_total` (lo
    # calcula el servicio sumando `orden_compra_detalle`).


class OrdenCompraUpdate(BaseModel):
    """Actualización parcial: todo opcional."""

    cotizacion_id: uuid.UUID | None = None
    estado_id: uuid.UUID | None = None
    fecha: date | None = None

    _no_nulos = rechazar_nulos("cotizacion_id", "estado_id", "fecha")


class OrdenCompraResponse(RespuestaBase):
    cotizacion_id: uuid.UUID
    estado_id: uuid.UUID
    fecha: date
    monto_total: Decimal
