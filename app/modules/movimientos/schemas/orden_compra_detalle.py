from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase, rechazar_nulos


class OrdenCompraDetalleCreate(BaseModel):
    orden_compra_id: uuid.UUID
    producto_id: uuid.UUID
    unidad_medida_id: uuid.UUID
    cantidad: int = Field(default=1, ge=1)
    precio_unitario: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class OrdenCompraDetalleUpdate(BaseModel):
    """Actualización parcial: todo opcional."""

    orden_compra_id: uuid.UUID | None = None
    producto_id: uuid.UUID | None = None
    unidad_medida_id: uuid.UUID | None = None
    cantidad: int | None = Field(default=None, ge=1)
    precio_unitario: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )

    _no_nulos = rechazar_nulos(
        "orden_compra_id",
        "producto_id",
        "unidad_medida_id",
        "cantidad",
        "precio_unitario",
    )


class OrdenCompraDetalleResponse(RespuestaBase):
    orden_compra_id: uuid.UUID
    producto_id: uuid.UUID
    unidad_medida_id: uuid.UUID
    cantidad: int
    precio_unitario: Decimal
