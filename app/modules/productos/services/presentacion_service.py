from __future__ import annotations

from app.core.crud import CRUDService
from app.modules.productos.models.presentacion import Presentacion


class PresentacionService(CRUDService[Presentacion]):
    modelo = Presentacion
    entidad = "Presentación"
    campos_unicos = {"descripcion": None, "codigo": None}
