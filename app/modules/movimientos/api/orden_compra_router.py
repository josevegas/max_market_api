from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.movimientos.schemas.orden_compra import (
    OrdenCompraCreate,
    OrdenCompraResponse,
    OrdenCompraUpdate,
)
from app.modules.movimientos.services.orden_compra_service import OrdenCompraService

router = crear_router_crud(
    prefijo="/ordenes-compra",
    etiqueta="Órdenes de compra",
    servicio=OrdenCompraService,
    schema_create=OrdenCompraCreate,
    schema_update=OrdenCompraUpdate,
    schema_response=OrdenCompraResponse,
    filtros={"cotizacion_id": UUID, "proveedor_id": UUID, "estado_id": UUID},
)
