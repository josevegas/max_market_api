from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.productos.schemas.sub_categoria import (
    SubCategoriaCreate,
    SubCategoriaResponse,
    SubCategoriaUpdate,
)
from app.modules.productos.services.sub_categoria_service import SubCategoriaService

router = crear_router_crud(
    prefijo="/sub-categorias",
    etiqueta="Sub categorías",
    servicio=SubCategoriaService,
    schema_create=SubCategoriaCreate,
    schema_update=SubCategoriaUpdate,
    schema_response=SubCategoriaResponse,
    filtros={"categoria_id": UUID},
)
