from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase, rechazar_nulos


class RequerimientoDetalleCreate(BaseModel):
    requerimiento_id: uuid.UUID
    producto_id: uuid.UUID
    unidad_medida_id: uuid.UUID
    cantidad: int = Field(default=1, ge=1)


class RequerimientoDetalleUpdate(BaseModel):
    """Actualización parcial: todo opcional."""

    requerimiento_id: uuid.UUID | None = None
    producto_id: uuid.UUID | None = None
    unidad_medida_id: uuid.UUID | None = None
    cantidad: int | None = Field(default=None, ge=1)

    _no_nulos = rechazar_nulos(
        "requerimiento_id", "producto_id", "unidad_medida_id", "cantidad"
    )


class RequerimientoDetalleResponse(RespuestaBase):
    requerimiento_id: uuid.UUID
    producto_id: uuid.UUID
    unidad_medida_id: uuid.UUID
    cantidad: int
