from __future__ import annotations

from typing import ClassVar

from app.modules.movimientos.models.cotizacion import Cotizacion
from app.modules.movimientos.models.pedido import Pedido
from app.modules.movimientos.services.cadena import DocumentoEncadenadoService


class CotizacionService(DocumentoEncadenadoService[Cotizacion]):
    """Solo se cotiza contra un pedido aprobado.

    Varios proveedores pueden cotizar el mismo pedido: no hay unicidad por
    `pedido_id`, que es justo lo que permite compararlas antes de ordenar.
    """

    modelo = Cotizacion
    entidad = "Cotización"
    campos_unicos: ClassVar[dict[str, str | None]] = {}

    padre: ClassVar[type] = Pedido
    campo_padre: ClassVar[str] = "pedido_id"
    entidad_padre: ClassVar[str] = "El pedido"
