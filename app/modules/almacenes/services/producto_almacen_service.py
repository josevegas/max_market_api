from __future__ import annotations

from typing import ClassVar

from app.core.crud import CRUDService
from app.modules.almacenes.models.producto_almacen import ProductoAlmacen


class ProductoAlmacenService(CRUDService[ProductoAlmacen]):
    modelo = ProductoAlmacen
    entidad = "Producto en almacén"
    campos_unicos: ClassVar[dict[str, str | None]] = {
        "producto_id": "almacen_id",
    }
