from __future__ import annotations

from typing import ClassVar

from app.core.crud import CRUDService
from app.modules.markets.models.sede import Sede


class SedeService(CRUDService[Sede]):
    modelo = Sede
    entidad = "Sede"
    campos_unicos: ClassVar[dict[str, str | None]] = {
        "nombre": "zona_id",
        "codigo": None,
    }
