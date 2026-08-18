from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.movimientos.schemas.recepcion_detalle import (
    RecepcionDetalleCreate,
    RecepcionDetalleResponse,
    RecepcionDetalleUpdate,
)
from app.modules.movimientos.services.recepcion_detalle_service import (
    RecepcionDetalleService,
)

router = crear_router_crud(
    prefijo="/recepciones-detalle",
    etiqueta="Detalle de recepciones",
    servicio=RecepcionDetalleService,
    schema_create=RecepcionDetalleCreate,
    schema_update=RecepcionDetalleUpdate,
    schema_response=RecepcionDetalleResponse,
    filtros={"recepcion_id": UUID, "producto_id": UUID},
)
