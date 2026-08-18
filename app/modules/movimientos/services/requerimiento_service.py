from __future__ import annotations

from typing import ClassVar

from app.modules.movimientos.models.pedido import Pedido
from app.modules.movimientos.models.pedido_detalle import PedidoDetalle
from app.modules.movimientos.models.requerimiento import Requerimiento
from app.modules.movimientos.models.requerimiento_detalle import RequerimientoDetalle
from app.modules.movimientos.services.generacion import GeneraSucesorAlAprobar


class RequerimientoService(GeneraSucesorAlAprobar[Requerimiento]):
    """Aprobar el requerimiento genera el pedido con las mismas líneas.

    Es el principio de la cadena: no tiene padre que validar, solo sucesor que
    producir.
    """

    modelo = Requerimiento
    entidad = "Requerimiento"
    campos_unicos: ClassVar[dict[str, str | None]] = {}

    sucesor: ClassVar[type] = Pedido
    campo_en_sucesor: ClassVar[str] = "requerimiento_id"
    detalle: ClassVar[type] = RequerimientoDetalle
    campo_detalle: ClassVar[str] = "requerimiento_id"
    detalle_sucesor: ClassVar[type] = PedidoDetalle
    campo_detalle_sucesor: ClassVar[str] = "pedido_id"
