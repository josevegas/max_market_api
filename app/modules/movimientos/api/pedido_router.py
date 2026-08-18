from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.movimientos.schemas.pedido import (
    PedidoCreate,
    PedidoResponse,
    PedidoUpdate,
)
from app.modules.movimientos.services.pedido_service import PedidoService

router = crear_router_crud(
    prefijo="/pedidos",
    etiqueta="Pedidos",
    servicio=PedidoService,
    schema_create=PedidoCreate,
    schema_update=PedidoUpdate,
    schema_response=PedidoResponse,
    filtros={"requerimiento_id": UUID, "estado_id": UUID},
)
