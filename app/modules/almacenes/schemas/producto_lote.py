from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase, rechazar_nulos

EstadoLote = Literal["disponible", "agotado", "inmovilizado"]


class ProductoLoteCreate(BaseModel):
    #: Dónde queda la mercadería: es lo que hace el stock comparable contra el
    #: `stock_minimo` de la ficha de `producto_almacen`.
    almacen_id: uuid.UUID
    #: Opcional: una recepción contra orden de compra directa no tiene guía.
    guia_remision_id: uuid.UUID | None = None
    #: Sin esto el lote no dice de qué producto es.
    producto_id: uuid.UUID
    fecha_ingreso: date
    cantidad: int = Field(default=0, ge=0)
    #: Lo que costó una unidad **de venta** de este lote. Cuando el lote entra
    #: por una recepción lo pone el servicio, convertido desde el precio de la
    #: línea; acá está para el alta manual.
    precio_compra: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=12, decimal_places=2
    )
    codigo_lote: str = Field(min_length=1, max_length=30)
    #: Opcional: no todo producto caduca. La columna admite null y la respuesta
    #: también, así que exigirlo al crear era una incoherencia.
    fecha_vencimiento: date | None = None
    dias_alerta_vencimiento: int | None = None
    estado: EstadoLote = "disponible"


class ProductoLoteUpdate(BaseModel):
    """Actualización parcial: todo opcional."""

    almacen_id: uuid.UUID | None = None
    guia_remision_id: uuid.UUID | None = None
    producto_id: uuid.UUID | None = None
    fecha_ingreso: date | None = None
    cantidad: int | None = Field(default=None, ge=0)
    precio_compra: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    codigo_lote: str | None = Field(default=None, min_length=1, max_length=30)
    fecha_vencimiento: date | None = None
    dias_alerta_vencimiento: int | None = None
    estado: EstadoLote | None = None

    # `fecha_vencimiento` sí admite null: un lote que no caduca.
    # `guia_remision_id` no entra: su columna admite NULL, así que mandarlo en
    # null es la forma de desligar el lote de la guía.
    _no_nulos = rechazar_nulos(
        "almacen_id",
        "producto_id",
        "fecha_ingreso",
        "cantidad",
        "precio_compra",
        "codigo_lote",
        "estado",
    )


class ProductoLoteResponse(RespuestaBase):
    almacen_id: uuid.UUID
    guia_remision_id: uuid.UUID | None = None
    producto_id: uuid.UUID
    fecha_ingreso: date
    cantidad: int
    precio_compra: Decimal
    codigo_lote: str
    fecha_vencimiento: date | None = None
    dias_alerta_vencimiento: int | None = None
    estado: str
