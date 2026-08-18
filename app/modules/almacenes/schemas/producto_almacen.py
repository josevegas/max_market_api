from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.shared.base import RespuestaBase, rechazar_nulos

#: Los mismos tres valores que admite el CHECK de la tabla. Como `Literal`, un
#: estado inventado se rechaza con un 422 que dice cuáles valen, en vez de
#: llegar a la base y volver como un error de integridad genérico.
EstadoProducto = Literal["disponible", "agotado", "inmovilizado"]


class ProductoAlmacenCreate(BaseModel):
    almacen_id: uuid.UUID
    producto_id: uuid.UUID
    unidad_medida_id: uuid.UUID
    stock_minimo: int = Field(default=1, ge=0)
    stock_maximo: int | None = Field(default=None, ge=0)
    # El nombre es el de la columna: antes decía `precio_venta` y el alta
    # fallaba con "invalid keyword argument" al construir el modelo.
    precio_venta_tienda: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    estado: EstadoProducto = "disponible"

    @model_validator(mode="after")
    def _maximo_sobre_minimo(self):
        if self.stock_maximo is not None and self.stock_maximo < self.stock_minimo:
            raise ValueError("stock_maximo no puede ser menor que stock_minimo")
        return self


class ProductoAlmacenUpdate(BaseModel):
    """Actualización parcial: todo opcional."""

    almacen_id: uuid.UUID | None = None
    producto_id: uuid.UUID | None = None
    unidad_medida_id: uuid.UUID | None = None
    stock_minimo: int | None = Field(default=None, ge=0)
    stock_maximo: int | None = Field(default=None, ge=0)
    precio_venta_tienda: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    estado: EstadoProducto | None = None

    # `stock_maximo` sí admite null en la tabla: quitarle el techo es legítimo.
    _no_nulos = rechazar_nulos(
        "almacen_id",
        "producto_id",
        "unidad_medida_id",
        "stock_minimo",
        "precio_venta_tienda",
        "estado",
    )


class ProductoAlmacenResponse(RespuestaBase):
    almacen_id: uuid.UUID
    producto_id: uuid.UUID
    unidad_medida_id: uuid.UUID
    stock_minimo: int
    stock_maximo: int | None = None
    precio_venta_tienda: Decimal
    estado: str
