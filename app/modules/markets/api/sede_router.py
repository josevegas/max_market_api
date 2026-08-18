from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.markets.schemas.sede import (
    SedeCreate,
    SedeResponse,
    SedeUpdate,
)
from app.modules.markets.services.sede_service import SedeService

router = crear_router_crud(
    prefijo="/sedes",
    etiqueta="Sedes",
    servicio=SedeService,
    schema_create=SedeCreate,
    schema_update=SedeUpdate,
    schema_response=SedeResponse,
    filtros={"zona_id": UUID},
)
