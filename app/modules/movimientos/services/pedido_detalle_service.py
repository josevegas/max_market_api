from __future__ import annotations

from typing import ClassVar

from app.core.crud import CRUDService
from app.modules.movimientos.models.pedido_detalle import PedidoDetalle


class PedidoDetalleService(CRUDService[PedidoDetalle]):
    modelo = PedidoDetalle
    entidad = "Línea de pedido"
    campos_unicos: ClassVar[dict[str, str | None]] = {
        "producto_id": "pedido_id",
    }
