from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.bancos.schemas.cuenta import (
    CuentaCreate,
    CuentaResponse,
    CuentaUpdate,
)
from app.modules.bancos.services.cuenta_service import CuentaService

router = crear_router_crud(
    prefijo="/cuentas",
    etiqueta="Cuentas bancarias",
    servicio=CuentaService,
    schema_create=CuentaCreate,
    schema_update=CuentaUpdate,
    schema_response=CuentaResponse,
    filtros={"empresa_id": UUID, "banco_id": UUID, "tipo_cuenta_id": UUID},
)
