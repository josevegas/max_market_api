from __future__ import annotations

from app.api.crud_router import crear_router_crud
from app.modules.productos.schemas.presentacion import (
    PresentacionCreate,
    PresentacionResponse,
    PresentacionUpdate,
)
from app.modules.productos.services.presentacion_service import PresentacionService

router = crear_router_crud(
    prefijo="/presentaciones",
    etiqueta="Presentaciones",
    servicio=PresentacionService,
    schema_create=PresentacionCreate,
    schema_update=PresentacionUpdate,
    schema_response=PresentacionResponse,
)
