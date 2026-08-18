from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase, rechazar_nulos

EstadoLote = Literal["disponible", "agotado", "inmovilizado"]


class ProductoLoteCreate(BaseModel):
    guia_remision_id: uuid.UUID
    #: Sin esto el lote no dice de qué producto es.
    producto_id: uuid.UUID
    unidad_medida_id: uuid.UUID
    fecha_ingreso: date
    cantidad: int = Field(default=0, ge=0)
    codigo_lote: str = Field(min_length=1, max_length=30)
    #: Opcional: no todo producto caduca. La columna admite null y la respuesta
    #: también, así que exigirlo al crear era una incoherencia.
    fecha_vencimiento: date | None = None
    estado: EstadoLote = "disponible"


class ProductoLoteUpdate(BaseModel):
    """Actualización parcial: todo opcional."""

    guia_remision_id: uuid.UUID | None = None
    producto_id: uuid.UUID | None = None
    unidad_medida_id: uuid.UUID | None = None
    fecha_ingreso: date | None = None
    cantidad: int | None = Field(default=None, ge=0)
    codigo_lote: str | None = Field(default=None, min_length=1, max_length=30)
    fecha_vencimiento: date | None = None
    estado: EstadoLote | None = None

    # `fecha_vencimiento` sí admite null: un lote que no caduca.
    _no_nulos = rechazar_nulos(
        "guia_remision_id",
        "producto_id",
        "unidad_medida_id",
        "fecha_ingreso",
        "cantidad",
        "codigo_lote",
        "estado",
    )


class ProductoLoteResponse(RespuestaBase):
    guia_remision_id: uuid.UUID
    producto_id: uuid.UUID
    unidad_medida_id: uuid.UUID
    fecha_ingreso: date
    cantidad: int
    codigo_lote: str
    fecha_vencimiento: date | None = None
    estado: str
