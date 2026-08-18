from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.movimientos.schemas.orden_compra_detalle import (
    OrdenCompraDetalleCreate,
    OrdenCompraDetalleResponse,
    OrdenCompraDetalleUpdate,
)
from app.modules.movimientos.services.orden_compra_detalle_service import (
    OrdenCompraDetalleService,
)

router = crear_router_crud(
    prefijo="/ordenes-compra-detalle",
    etiqueta="Líneas de orden de compra",
    servicio=OrdenCompraDetalleService,
    schema_create=OrdenCompraDetalleCreate,
    schema_update=OrdenCompraDetalleUpdate,
    schema_response=OrdenCompraDetalleResponse,
    filtros={"orden_compra_id": UUID, "producto_id": UUID},
)
