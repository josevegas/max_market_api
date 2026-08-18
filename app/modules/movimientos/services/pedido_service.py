from __future__ import annotations

from typing import ClassVar

from app.modules.movimientos.models.pedido import Pedido
from app.modules.movimientos.models.requerimiento import Requerimiento
from app.modules.movimientos.services.cadena import DocumentoEncadenadoService


class PedidoService(DocumentoEncadenadoService[Pedido]):
    """Un pedido solo nace de un requerimiento aprobado."""

    modelo = Pedido
    entidad = "Pedido"
    campos_unicos: ClassVar[dict[str, str | None]] = {}

    padre: ClassVar[type] = Requerimiento
    campo_padre: ClassVar[str] = "requerimiento_id"
    entidad_padre: ClassVar[str] = "El requerimiento"
