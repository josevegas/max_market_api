from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.productos.schemas.categoria import (
    CategoriaCreate,
    CategoriaResponse,
    CategoriaUpdate,
)
from app.modules.productos.services.categoria_service import CategoriaService

router = crear_router_crud(
    prefijo="/categorias",
    etiqueta="Categorías",
    servicio=CategoriaService,
    schema_create=CategoriaCreate,
    schema_update=CategoriaUpdate,
    schema_response=CategoriaResponse,
    filtros={"sub_familia_id": UUID},
)
