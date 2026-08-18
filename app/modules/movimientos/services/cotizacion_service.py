from __future__ import annotations

from typing import ClassVar

from app.modules.movimientos.models.cotizacion import Cotizacion
from app.modules.movimientos.models.cotizacion_detalle import CotizacionDetalle
from app.modules.movimientos.models.orden_compra import OrdenCompra
from app.modules.movimientos.models.orden_compra_detalle import OrdenCompraDetalle
from app.modules.movimientos.models.pedido import Pedido
from app.modules.movimientos.services.cadena import DocumentoEncadenadoService
from app.modules.movimientos.services.generacion import GeneraSucesorAlAprobar


class CotizacionService(
    GeneraSucesorAlAprobar[Cotizacion], DocumentoEncadenadoService[Cotizacion]
):
    """Solo se cotiza contra un pedido aprobado, y aprobarla emite la orden.

    Varios proveedores pueden cotizar el mismo pedido: no hay unicidad por
    `pedido_id`, que es justo lo que permite compararlas antes de ordenar.
    Aprobar una es elegir a ese proveedor, y de ahí que genere la orden de
    compra con sus precios ya puestos.
    """

    modelo = Cotizacion
    entidad = "Cotización"
    campos_unicos: ClassVar[dict[str, str | None]] = {}

    padre: ClassVar[type] = Pedido
    campo_padre: ClassVar[str] = "pedido_id"
    entidad_padre: ClassVar[str] = "El pedido"

    sucesor: ClassVar[type] = OrdenCompra
    campo_en_sucesor: ClassVar[str] = "cotizacion_id"
    detalle: ClassVar[type] = CotizacionDetalle
    campo_detalle: ClassVar[str] = "cotizacion_id"
    detalle_sucesor: ClassVar[type] = OrdenCompraDetalle
    campo_detalle_sucesor: ClassVar[str] = "orden_compra_id"
    # La orden compra lo cotizado al precio cotizado: es el compromiso con el
    # proveedor, así que arrastra precios y total.
    sucesor_con_precio: ClassVar[bool] = True
    sucesor_con_total: ClassVar[bool] = True
