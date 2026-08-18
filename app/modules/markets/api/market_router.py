from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.markets.schemas.market import (
    MarketCreate,
    MarketResponse,
    MarketUpdate,
)
from app.modules.markets.services.market_service import MarketService

router = crear_router_crud(
    prefijo="/markets",
    etiqueta="Markets",
    servicio=MarketService,
    schema_create=MarketCreate,
    schema_update=MarketUpdate,
    schema_response=MarketResponse,
    filtros={"sede_id": UUID},
)
