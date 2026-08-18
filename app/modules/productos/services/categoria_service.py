from __future__ import annotations

from typing import ClassVar

from app.core.crud import CRUDService
from app.modules.productos.models.categoria import Categoria


class CategoriaService(CRUDService[Categoria]):
    modelo = Categoria
    entidad = "Categoría"
    campos_unicos: ClassVar[dict[str, str | None]] = {
        "nombre": "sub_familia_id",
        "codigo": None,
    }
