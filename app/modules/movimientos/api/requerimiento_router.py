from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.movimientos.schemas.requerimiento import (
    RequerimientoCreate,
    RequerimientoResponse,
    RequerimientoUpdate,
)
from app.modules.movimientos.services.requerimiento_service import RequerimientoService

router = crear_router_crud(
    prefijo="/requerimientos",
    etiqueta="Requerimientos",
    servicio=RequerimientoService,
    schema_create=RequerimientoCreate,
    schema_update=RequerimientoUpdate,
    schema_response=RequerimientoResponse,
    filtros={"almacen_id": UUID, "estado_id": UUID},
)
