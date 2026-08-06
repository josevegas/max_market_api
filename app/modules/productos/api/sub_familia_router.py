from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.productos.schemas.sub_familia import (
    SubFamiliaCreate,
    SubFamiliaResponse,
    SubFamiliaUpdate,
)
from app.modules.productos.services.sub_familia_service import SubFamiliaService

router = crear_router_crud(
    prefijo="/sub-familias",
    etiqueta="Sub familias",
    servicio=SubFamiliaService,
    schema_create=SubFamiliaCreate,
    schema_update=SubFamiliaUpdate,
    schema_response=SubFamiliaResponse,
    filtros={"familia_id": UUID},
)
