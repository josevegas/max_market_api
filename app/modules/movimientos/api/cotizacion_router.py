from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.movimientos.schemas.cotizacion import (
    CotizacionCreate,
    CotizacionResponse,
    CotizacionUpdate,
)
from app.modules.movimientos.services.cotizacion_service import CotizacionService

router = crear_router_crud(
    prefijo="/cotizaciones",
    etiqueta="Cotizaciones",
    servicio=CotizacionService,
    schema_create=CotizacionCreate,
    schema_update=CotizacionUpdate,
    schema_response=CotizacionResponse,
    filtros={"pedido_id": UUID, "proveedor_id": UUID, "estado_id": UUID},
)
