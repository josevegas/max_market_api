from __future__ import annotations

from app.api.crud_router import crear_router_crud
from app.modules.markets.schemas.zona import (
    ZonaCreate,
    ZonaResponse,
    ZonaUpdate,
)
from app.modules.markets.services.zona_service import ZonaService

router = crear_router_crud(
    prefijo="/zonas",
    etiqueta="Zonas",
    servicio=ZonaService,
    schema_create=ZonaCreate,
    schema_update=ZonaUpdate,
    schema_response=ZonaResponse,
)
