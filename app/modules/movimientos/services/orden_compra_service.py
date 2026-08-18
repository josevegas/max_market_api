from __future__ import annotations

from typing import ClassVar

from app.modules.movimientos.models.cotizacion import Cotizacion
from app.modules.movimientos.models.orden_compra import OrdenCompra
from app.modules.movimientos.services.cadena import DocumentoEncadenadoService


class OrdenCompraService(DocumentoEncadenadoService[OrdenCompra]):
    """La orden se emite contra la cotización que se aprobó, y solo esa."""

    modelo = OrdenCompra
    entidad = "Orden de compra"
    campos_unicos: ClassVar[dict[str, str | None]] = {}

    padre: ClassVar[type] = Cotizacion
    campo_padre: ClassVar[str] = "cotizacion_id"
    entidad_padre: ClassVar[str] = "La cotización"
