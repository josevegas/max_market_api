from __future__ import annotations

from typing import ClassVar

from app.core.crud import CRUDService
from app.modules.markets.models.market import Market


class MarketService(CRUDService[Market]):
    modelo = Market
    entidad = "Market"
    campos_unicos: ClassVar[dict[str, str | None]] = {
        "nombre": "sede_id",
        "codigo": None,
    }
