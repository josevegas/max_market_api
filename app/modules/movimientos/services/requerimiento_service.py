from __future__ import annotations

from typing import ClassVar

from app.core.crud import CRUDService
from app.modules.movimientos.models.requerimiento import Requerimiento


class RequerimientoService(CRUDService[Requerimiento]):
    modelo = Requerimiento
    entidad = "Requerimiento"
    campos_unicos: ClassVar[dict[str, str | None]] = {}
