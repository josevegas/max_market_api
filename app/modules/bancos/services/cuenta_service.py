from __future__ import annotations

from typing import ClassVar

from app.core.crud import CRUDService
from app.modules.bancos.models.cuenta import Cuenta


class CuentaService(CRUDService[Cuenta]):
    modelo = Cuenta
    entidad = "Cuenta"
    campos_unicos: ClassVar[dict[str, str | None]] = {
        "numero_cuenta": "banco_id",
    }
