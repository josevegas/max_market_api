from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.movimientos.schemas.cotizacion_detalle import (
    CotizacionDetalleCreate,
    CotizacionDetalleResponse,
    CotizacionDetalleUpdate,
)
from app.modules.movimientos.services.cotizacion_detalle_service import (
    CotizacionDetalleService,
)

router = crear_router_crud(
    prefijo="/cotizaciones-detalle",
    etiqueta="Líneas de cotización",
    servicio=CotizacionDetalleService,
    schema_create=CotizacionDetalleCreate,
    schema_update=CotizacionDetalleUpdate,
    schema_response=CotizacionDetalleResponse,
    filtros={"cotizacion_id": UUID, "producto_id": UUID},
)
