from __future__ import annotations

from typing import ClassVar

from app.core.crud import CRUDService
from app.modules.bancos.models.tipo_cuenta import TipoCuenta


class TipoCuentaService(CRUDService[TipoCuenta]):
    modelo = TipoCuenta
    entidad = "Tipo de cuenta"
    campos_unicos: ClassVar[dict[str, str | None]] = {
        "descripcion": None,
        "codigo": None,
    }
