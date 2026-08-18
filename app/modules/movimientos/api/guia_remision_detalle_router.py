from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.movimientos.schemas.guia_remision_detalle import (
    GuiaRemisionDetalleCreate,
    GuiaRemisionDetalleResponse,
    GuiaRemisionDetalleUpdate,
)
from app.modules.movimientos.services.guia_remision_detalle_service import (
    GuiaRemisionDetalleService,
)

router = crear_router_crud(
    prefijo="/guias-remision-detalle",
    etiqueta="Líneas de guía de remisión",
    servicio=GuiaRemisionDetalleService,
    schema_create=GuiaRemisionDetalleCreate,
    schema_update=GuiaRemisionDetalleUpdate,
    schema_response=GuiaRemisionDetalleResponse,
    filtros={"guia_remision_id": UUID, "producto_id": UUID},
)
