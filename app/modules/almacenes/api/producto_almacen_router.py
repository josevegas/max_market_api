from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.almacenes.schemas.producto_almacen import (
    ProductoAlmacenCreate,
    ProductoAlmacenResponse,
    ProductoAlmacenUpdate,
)
from app.modules.almacenes.services.producto_almacen_service import (
    ProductoAlmacenService,
)

router = crear_router_crud(
    prefijo="/productos-almacen",
    etiqueta="Productos en almacén",
    servicio=ProductoAlmacenService,
    schema_create=ProductoAlmacenCreate,
    schema_update=ProductoAlmacenUpdate,
    schema_response=ProductoAlmacenResponse,
    filtros={"almacen_id": UUID, "producto_id": UUID, "estado": str},
)
