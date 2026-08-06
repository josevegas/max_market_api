from __future__ import annotations

from app.core.crud import CRUDService
from app.modules.productos.models.categoria import Categoria


class CategoriaService(CRUDService[Categoria]):
    modelo = Categoria
    entidad = "Categoría"
