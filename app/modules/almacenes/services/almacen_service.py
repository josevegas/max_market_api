from __future__ import annotations

from typing import ClassVar

from app.core.crud import CRUDService
from app.modules.almacenes.models.almacen import Almacen


class AlmacenService(CRUDService[Almacen]):
    modelo = Almacen
    entidad = "Almacén"
    campos_unicos: ClassVar[dict[str, str | None]] = {
        "nombre": "market_id",
        "codigo": None,
    }
