from __future__ import annotations

from app.core.crud import CRUDService
from app.modules.productos.models.familia import Familia


class FamiliaService(CRUDService[Familia]):
    modelo = Familia
    entidad = "Familia"
