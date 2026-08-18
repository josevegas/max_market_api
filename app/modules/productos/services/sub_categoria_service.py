from __future__ import annotations

from typing import ClassVar

from app.core.crud import CRUDService
from app.modules.productos.models.sub_categoria import SubCategoria


class SubCategoriaService(CRUDService[SubCategoria]):
    modelo = SubCategoria
    entidad = "Sub categoría"
    campos_unicos: ClassVar[dict[str, str | None]] = {
        "nombre": "categoria_id",
        "codigo": None,
    }
