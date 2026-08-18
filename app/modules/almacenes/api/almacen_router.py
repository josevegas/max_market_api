from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.almacenes.schemas.almacen import (
    AlmacenCreate,
    AlmacenResponse,
    AlmacenUpdate,
)
from app.modules.almacenes.services.almacen_service import AlmacenService

router = crear_router_crud(
    prefijo="/almacenes",
    etiqueta="Almacenes",
    servicio=AlmacenService,
    schema_create=AlmacenCreate,
    schema_update=AlmacenUpdate,
    schema_response=AlmacenResponse,
    filtros={"market_id": UUID},
)
