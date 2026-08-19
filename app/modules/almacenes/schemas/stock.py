from __future__ import annotations

import uuid

from pydantic import BaseModel


class StockDeProductoResponse(BaseModel):
    """Lo disponible de un producto en un almacén, contra su mínimo."""

    producto_id: uuid.UUID
    #: En qué unidad está `disponible`. Va explícito porque el mínimo de la
    #: ficha puede estar en otra, y sin decirlo el número sería ambiguo.
    unidad_venta_id: uuid.UUID
    disponible: int
    stock_minimo: int | None = None
    stock_maximo: int | None = None
    #: Ya comparado en unidad mínima: la ficha y el lote no tienen por qué
    #: estar en la misma unidad, así que el cliente no puede deducirlo de los
    #: dos números de arriba.
    bajo_minimo: bool
    #: `False` cuando hay mercadería pero nadie creó la ficha del producto en
    #: este almacén: hay stock sin un mínimo contra el cual medirlo.
    tiene_ficha: bool
