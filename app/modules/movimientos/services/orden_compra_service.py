from __future__ import annotations

from typing import ClassVar

from app.modules.movimientos.models.cotizacion import Cotizacion
from app.modules.movimientos.models.guia_remision import GuiaRemision
from app.modules.movimientos.models.guia_remision_detalle import GuiaRemisionDetalle
from app.modules.movimientos.models.orden_compra import OrdenCompra
from app.modules.movimientos.models.orden_compra_detalle import OrdenCompraDetalle
from app.modules.movimientos.services.cadena import (
    DocumentoEncadenadoService,
    NaceEnPendiente,
)
from app.modules.movimientos.services.generacion import GeneraSucesorAlAprobar


class OrdenCompraService(
    NaceEnPendiente[OrdenCompra],
    GeneraSucesorAlAprobar[OrdenCompra],
    DocumentoEncadenadoService[OrdenCompra],
):
    """La orden se emite contra la cotización que se aprobó, y solo esa.

    Aprobarla abre la guía de remisión con lo que se espera recibir. La guía no
    mueve dinero: nace con las cantidades de la orden y el proveedor confirmará
    cuánto entregó de verdad.
    """

    modelo = OrdenCompra
    entidad = "Orden de compra"
    campos_unicos: ClassVar[dict[str, str | None]] = {}

    padre: ClassVar[type] = Cotizacion
    campo_padre: ClassVar[str] = "cotizacion_id"
    entidad_padre: ClassVar[str] = "La cotización"

    sucesor: ClassVar[type] = GuiaRemision
    campo_en_sucesor: ClassVar[str] = "orden_compra_id"
    detalle: ClassVar[type] = OrdenCompraDetalle
    campo_detalle: ClassVar[str] = "orden_compra_id"
    detalle_sucesor: ClassVar[type] = GuiaRemisionDetalle
    campo_detalle_sucesor: ClassVar[str] = "guia_remision_id"
