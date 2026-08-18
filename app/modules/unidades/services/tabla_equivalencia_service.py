from __future__ import annotations

from typing import ClassVar

from app.core.crud import CRUDService
from app.modules.unidades.models.tabla_equivalencia import TablaEquivalencia


class TablaEquivalenciaService(CRUDService[TablaEquivalencia]):
    modelo = TablaEquivalencia
    entidad = "Tabla de equivalencia"
    campos_unicos: ClassVar[dict[str, str | None]] = {}
