from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.productos.schemas.precio_producto import (
    PrecioProductoCreate,
    PrecioProductoResponse,
    PrecioProductoUpdate,
)
from app.modules.productos.services.precio_producto_service import PrecioProductoService

router = crear_router_crud(
    prefijo="/precios",
    etiqueta="Precios",
    servicio=PrecioProductoService,
    schema_create=PrecioProductoCreate,
    schema_update=PrecioProductoUpdate,
    schema_response=PrecioProductoResponse,
    filtros={"producto_id": UUID},
)
