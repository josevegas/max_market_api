from __future__ import annotations

from app.api.crud_router import crear_router_crud
from app.modules.unidades.schemas.unidad_medida import (
    UnidadMedidaCreate,
    UnidadMedidaResponse,
    UnidadMedidaUpdate,
)
from app.modules.unidades.services.unidad_medida_service import UnidadMedidaService

router = crear_router_crud(
    prefijo="/unidades-medida",
    etiqueta="Unidades de medida",
    servicio=UnidadMedidaService,
    schema_create=UnidadMedidaCreate,
    schema_update=UnidadMedidaUpdate,
    schema_response=UnidadMedidaResponse,
)
