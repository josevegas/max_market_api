from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.movimientos.schemas.guia_remision import (
    GuiaRemisionCreate,
    GuiaRemisionResponse,
    GuiaRemisionUpdate,
)
from app.modules.movimientos.services.guia_remision_service import GuiaRemisionService

router = crear_router_crud(
    prefijo="/guias-remision",
    etiqueta="Guías de remisión",
    servicio=GuiaRemisionService,
    schema_create=GuiaRemisionCreate,
    schema_update=GuiaRemisionUpdate,
    schema_response=GuiaRemisionResponse,
    filtros={"orden_compra_id": UUID, "estado_id": UUID},
)
