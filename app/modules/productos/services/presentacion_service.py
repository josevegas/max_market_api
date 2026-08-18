from __future__ import annotations

from typing import ClassVar

from app.core.crud import CRUDService
from app.modules.productos.models.presentacion import Presentacion


class PresentacionService(CRUDService[Presentacion]):
    modelo = Presentacion
    entidad = "Presentación"
    campos_unicos: ClassVar[dict[str, str | None]] = {
        "descripcion": None,
        "codigo": None,
    }
