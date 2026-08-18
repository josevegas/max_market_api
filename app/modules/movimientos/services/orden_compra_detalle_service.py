from __future__ import annotations

from typing import ClassVar

from app.modules.movimientos.models.orden_compra import OrdenCompra
from app.modules.movimientos.models.orden_compra_detalle import OrdenCompraDetalle
from app.modules.movimientos.services.detalle_con_total import DetalleConTotalService


class OrdenCompraDetalleService(DetalleConTotalService[OrdenCompraDetalle]):
    modelo = OrdenCompraDetalle
    entidad = "Línea de orden de compra"

    cabecera: ClassVar[type] = OrdenCompra
    campo_cabecera: ClassVar[str] = "orden_compra_id"
    #: La línea no almacena importe: el total se suma desde cantidad y precio.
    campo_monto: ClassVar[str | None] = None
