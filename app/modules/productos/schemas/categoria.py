from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.modules.productos.schemas.base import RespuestaBase


class CategoriaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    codigo: str | None = Field(default=None, max_length=10)
    sub_familia_id: uuid.UUID
    #: Porcentaje de margen; no puede ser negativo.
    margen_ganancia: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class CategoriaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    codigo: str | None = Field(default=None, max_length=10)
    sub_familia_id: uuid.UUID | None = None
    margen_ganancia: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )


class CategoriaResponse(RespuestaBase):
    nombre: str
    codigo: str | None = None
    sub_familia_id: uuid.UUID
    margen_ganancia: Decimal
