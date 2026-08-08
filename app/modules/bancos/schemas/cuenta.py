from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.shared.base import RespuestaBase


class CuentaCreate(BaseModel):
    numero_cuenta: str
    banco_id: uuid.UUID
    empresa_id: uuid.UUID
    tipo_cuenta_id: uuid.UUID
    moneda: str


class CuentaUpdate(BaseModel):
    numero_cuenta: str | None
    banco_id: uuid.UUID | None
    empresa_id: uuid.UUID | None
    tipo_cuenta_id: uuid.UUID | None
    moneda: str | None


class CuentaResponse(RespuestaBase):
    numero_cuenta: str
    banco_id: uuid.UUID
    empresa_id: uuid.UUID
    tipo_cuenta_id: uuid.UUID
    moneda: str
