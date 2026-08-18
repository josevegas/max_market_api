from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase, rechazar_nulos

#: Monedas admitidas. Cerrado a propósito: como texto libre acabarían
#: conviviendo "PEN", "pen", "S/" y "soles" como cuatro valores distintos que
#: luego nadie puede agrupar. La columna sigue siendo String(10), así que
#: sumar una moneda no exige migración.
Moneda = Literal["PEN", "USD"]


class CuentaCreate(BaseModel):
    numero_cuenta: str = Field(min_length=1, max_length=20)
    banco_id: uuid.UUID
    empresa_id: uuid.UUID
    tipo_cuenta_id: uuid.UUID
    moneda: Moneda


class CuentaUpdate(BaseModel):
    """Actualización parcial: todo opcional (ver `ZonaUpdate` en markets)."""

    numero_cuenta: str | None = Field(default=None, min_length=1, max_length=20)
    banco_id: uuid.UUID | None = None
    empresa_id: uuid.UUID | None = None
    tipo_cuenta_id: uuid.UUID | None = None
    moneda: Moneda | None = None

    # Columnas NOT NULL: omitirlas es válido, mandarlas como null no.
    _no_nulos = rechazar_nulos(
        "numero_cuenta", "banco_id", "empresa_id", "tipo_cuenta_id", "moneda"
    )


class CuentaResponse(RespuestaBase):
    numero_cuenta: str
    banco_id: uuid.UUID
    empresa_id: uuid.UUID
    tipo_cuenta_id: uuid.UUID
    moneda: str
