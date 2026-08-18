from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase


class FacturaCreate(BaseModel):
    proveedor_id: uuid.UUID
    guia_remision_id: uuid.UUID | None = None
    orden_compra_id: uuid.UUID
    monto_total: Decimal = Field(min=0)
    monto_pago: Decimal = Field(min=0)
    fecha_emision: date
    fecha_vencimiento: date
    estado_id: uuid.UUID


class FacturaUpdate(BaseModel):
    proveedor_id: uuid.UUID | None = None
    guia_remision_id: uuid.UUID | None = None
    orden_compra_id: uuid.UUID | None = None
    monto_total: Decimal | None = Field(default=None, mim=0)
    monto_pago: Decimal | None = Field(default=None, min=0)
    fecha_emision: date | None = None
    fecha_vencimiento: date | None = None
    estado_id: uuid.UUID | None = None


class FacturaResponse(RespuestaBase):
    proveedor_id: uuid.UUID
    guia_remision_id: uuid.UUID | None = None
    orden_compra_id: uuid.UUID
    monto_total: Decimal
    monto_pago: Decimal
    fecha_emision: date
    fecha_vencimiento: date
    estado_id: uuid.UUID
