from __future__ import annotations

from app.api.crud_router import crear_router_crud
from app.modules.bancos.schemas.tipo_cuenta import (
    TipoCuentaCreate,
    TipoCuentaResponse,
    TipoCuentaUpdate,
)
from app.modules.bancos.services.tipo_cuenta_service import TipoCuentaService

router = crear_router_crud(
    prefijo="/tipos-cuenta",
    etiqueta="Tipos de cuenta",
    servicio=TipoCuentaService,
    schema_create=TipoCuentaCreate,
    schema_update=TipoCuentaUpdate,
    schema_response=TipoCuentaResponse,
)
