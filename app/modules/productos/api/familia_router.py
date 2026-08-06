from __future__ import annotations

from app.api.crud_router import crear_router_crud
from app.modules.productos.schemas.familia import (
    FamiliaCreate,
    FamiliaResponse,
    FamiliaUpdate,
)
from app.modules.productos.services.familia_service import FamiliaService

router = crear_router_crud(
    prefijo="/familias",
    etiqueta="Familias",
    servicio=FamiliaService,
    schema_create=FamiliaCreate,
    schema_update=FamiliaUpdate,
    schema_response=FamiliaResponse,
)
