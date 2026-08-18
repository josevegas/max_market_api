from __future__ import annotations

from typing import ClassVar

from app.core.crud import CRUDService
from app.modules.productos.models.sub_familia import SubFamilia


class SubFamiliaService(CRUDService[SubFamilia]):
    modelo = SubFamilia
    entidad = "Sub familia"
    campos_unicos: ClassVar[dict[str, str | None]] = {
        "nombre": "familia_id",
        "codigo": None,
    }
