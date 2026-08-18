from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.movimientos.schemas.requerimiento_detalle import (
    RequerimientoDetalleCreate,
    RequerimientoDetalleResponse,
    RequerimientoDetalleUpdate,
)
from app.modules.movimientos.services.requerimiento_detalle_service import (
    RequerimientoDetalleService,
)

router = crear_router_crud(
    prefijo="/requerimientos-detalle",
    etiqueta="Líneas de requerimiento",
    servicio=RequerimientoDetalleService,
    schema_create=RequerimientoDetalleCreate,
    schema_update=RequerimientoDetalleUpdate,
    schema_response=RequerimientoDetalleResponse,
    filtros={"requerimiento_id": UUID, "producto_id": UUID},
)
