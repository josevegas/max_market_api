from __future__ import annotations

from typing import ClassVar

from app.core.crud import CRUDService
from app.modules.bancos.models.banco import Banco


class BancoService(CRUDService[Banco]):
    modelo = Banco
    entidad = "Banco"
    campos_unicos: ClassVar[dict[str, str | None]] = {
        "ruc": None,
        "codigo": None,
    }
