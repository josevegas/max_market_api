from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase, rechazar_nulos


class PedidoDetalleCreate(BaseModel):
    pedido_id: uuid.UUID
    producto_id: uuid.UUID
    unidad_medida_id: uuid.UUID
    cantidad: int = Field(default=1, ge=1)


class PedidoDetalleUpdate(BaseModel):
    """Actualización parcial: todo opcional."""

    pedido_id: uuid.UUID | None = None
    producto_id: uuid.UUID | None = None
    unidad_medida_id: uuid.UUID | None = None
    cantidad: int | None = Field(default=None, ge=1)

    _no_nulos = rechazar_nulos(
        "pedido_id", "producto_id", "unidad_medida_id", "cantidad"
    )


class PedidoDetalleResponse(RespuestaBase):
    pedido_id: uuid.UUID
    producto_id: uuid.UUID
    unidad_medida_id: uuid.UUID
    cantidad: int
