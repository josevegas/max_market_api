"""Piezas comunes a los schemas del módulo."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RespuestaBase(BaseModel):
    """Campos que toda respuesta arrastra: identidad y auditoría.

    Son de solo lectura: los pone el servidor, nunca el cliente. Por eso no
    aparecen en los schemas de creación ni de actualización.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: uuid.UUID | None = None
    updated_by: uuid.UUID | None = None
