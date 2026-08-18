from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.movimientos.schemas.pedido_detalle import (
    PedidoDetalleCreate,
    PedidoDetalleResponse,
    PedidoDetalleUpdate,
)
from app.modules.movimientos.services.pedido_detalle_service import PedidoDetalleService

router = crear_router_crud(
    prefijo="/pedidos-detalle",
    etiqueta="Líneas de pedido",
    servicio=PedidoDetalleService,
    schema_create=PedidoDetalleCreate,
    schema_update=PedidoDetalleUpdate,
    schema_response=PedidoDetalleResponse,
    filtros={"pedido_id": UUID, "producto_id": UUID},
)
