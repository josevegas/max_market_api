from __future__ import annotations

from app.api.crud_router import crear_router_crud
from app.modules.bancos.schemas.banco import (
    BancoCreate,
    BancoResponse,
    BancoUpdate,
)
from app.modules.bancos.services.banco_service import BancoService

router = crear_router_crud(
    prefijo="/bancos",
    etiqueta="Bancos",
    servicio=BancoService,
    schema_create=BancoCreate,
    schema_update=BancoUpdate,
    schema_response=BancoResponse,
)
