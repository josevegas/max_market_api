from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.almacenes.schemas.producto_lote import (
    ProductoLoteCreate,
    ProductoLoteResponse,
    ProductoLoteUpdate,
)
from app.modules.almacenes.services.producto_lote_service import ProductoLoteService

router = crear_router_crud(
    prefijo="/productos-lote",
    etiqueta="Lotes de producto",
    servicio=ProductoLoteService,
    schema_create=ProductoLoteCreate,
    schema_update=ProductoLoteUpdate,
    schema_response=ProductoLoteResponse,
    filtros={"guia_remision_id": UUID, "producto_id": UUID, "estado": str},
)
