from __future__ import annotations

from typing import ClassVar

from app.modules.movimientos.models.guia_remision import GuiaRemision
from app.modules.movimientos.models.orden_compra import OrdenCompra
from app.modules.movimientos.services.cadena import DocumentoEncadenadoService


class GuiaRemisionService(DocumentoEncadenadoService[GuiaRemision]):
    """La guía documenta lo que trae el proveedor contra una orden aprobada."""

    modelo = GuiaRemision
    entidad = "Guía de remisión"
    campos_unicos: ClassVar[dict[str, str | None]] = {}

    padre: ClassVar[type] = OrdenCompra
    campo_padre: ClassVar[str] = "orden_compra_id"
    entidad_padre: ClassVar[str] = "La orden de compra"
