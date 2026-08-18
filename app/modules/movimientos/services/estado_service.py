from __future__ import annotations

from typing import ClassVar

from app.core.crud import CRUDService
from app.modules.movimientos.models.estado import Estado


class EstadoService(CRUDService[Estado]):
    modelo = Estado
    entidad = "Estado"
    campos_unicos: ClassVar[dict[str, str | None]] = {
        "descripcion": None,
        "codigo": None,
    }
