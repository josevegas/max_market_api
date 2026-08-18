from __future__ import annotations

from typing import ClassVar

from app.core.crud import CRUDService
from app.modules.markets.models.zona import Zona


class ZonaService(CRUDService[Zona]):
    modelo = Zona
    entidad = "Zona"
    campos_unicos: ClassVar[dict[str, str | None]] = {
        "nombre": None,
        "codigo": None,
    }
