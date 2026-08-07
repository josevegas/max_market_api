from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.shareds.base import RespuestaBase


class PrecioProductoCreate(BaseModel):
    producto_id: uuid.UUID
    precio_compra: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    precio_venta: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    fecha_inicio: date
    #: Sin fecha de fin, el precio rige hasta nuevo aviso.
    fecha_fin: date | None = None

    @model_validator(mode="after")
    def _vigencia_coherente(self):
        # Misma regla que el CHECK de la tabla: se valida acá para devolver un
        # 422 explicativo en lugar de un error de integridad.
        if self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValueError("fecha_fin no puede ser anterior a fecha_inicio.")
        return self


class PrecioProductoUpdate(BaseModel):
    precio_compra: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    precio_venta: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    fecha_inicio: date | None = None
    fecha_fin: date | None = None


class PrecioProductoResponse(RespuestaBase):
    producto_id: uuid.UUID
    precio_compra: Decimal
    precio_venta: Decimal
    fecha_inicio: date
    fecha_fin: date | None = None
