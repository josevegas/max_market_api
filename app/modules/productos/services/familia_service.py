from __future__ import annotations

from typing import ClassVar

from app.core.crud import CRUDService
from app.modules.productos.models.familia import Familia


class FamiliaService(CRUDService[Familia]):
    modelo = Familia
    entidad = "Familia"
    campos_unicos: ClassVar[dict[str, str | None]] = {"nombre": None, "codigo": None}
