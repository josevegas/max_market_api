from __future__ import annotations

from typing import ClassVar

from app.core.crud import CRUDService
from app.modules.movimientos.models.requerimiento_detalle import RequerimientoDetalle


class RequerimientoDetalleService(CRUDService[RequerimientoDetalle]):
    modelo = RequerimientoDetalle
    entidad = "Línea de requerimiento"
    campos_unicos: ClassVar[dict[str, str | None]] = {
        "producto_id": "requerimiento_id",
    }
