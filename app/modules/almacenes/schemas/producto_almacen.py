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
    #: Opcional: por defecto lo calcula el stock, a partir del lote más caro
    #: que quede con existencias. Solo hace falta enviarlo junto con
    #: `precio_manual`, para fijarlo a mano.
    precio_venta_tienda: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    #: Con `True` la sincronización no vuelve a tocar el precio: es la tienda
    #: la que decide, por ejemplo en una promoción.
    precio_manual: bool = False
    estado: EstadoProducto = "disponible"

    @model_validator(mode="after")
    def _coherente(self):
        if self.stock_maximo is not None and self.stock_maximo < self.stock_minimo:
            raise ValueError("stock_maximo no puede ser menor que stock_minimo")
        # Fijar el precio a mano sin decir cuál dejaría la ficha con el precio
        # congelado en cero, y la sincronización no volvería a corregirlo.
        if self.precio_manual and self.precio_venta_tienda is None:
            raise ValueError(
                "precio_venta_tienda es obligatorio cuando precio_manual es true."
            )
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
    #: Ponerlo en `False` devuelve la ficha al precio calculado; la próxima
    #: entrada de stock lo recalcula.
    precio_manual: bool | None = None
    estado: EstadoProducto | None = None

    # `stock_maximo` sí admite null en la tabla: quitarle el techo es legítimo.
    _no_nulos = rechazar_nulos(
        "almacen_id",
        "producto_id",
        "unidad_medida_id",
        "stock_minimo",
        "precio_venta_tienda",
        "precio_manual",
        "estado",
    )


class ProductoAlmacenResponse(RespuestaBase):
    almacen_id: uuid.UUID
    producto_id: uuid.UUID
    unidad_medida_id: uuid.UUID
    stock_minimo: int
    stock_maximo: int | None = None
    precio_venta_tienda: Decimal
    precio_manual: bool
    estado: str
