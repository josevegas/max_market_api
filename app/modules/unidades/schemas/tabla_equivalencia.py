from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase, rechazar_nulos


class TablaEquivalenciaCreate(BaseModel):
    unidad_medida_id: uuid.UUID
    #: Cuántas unidades base equivale. `0` dejaría una conversión que anula
    #: cualquier cantidad, y negativo no significa nada.
    factor_conversion: int = Field(default=1, ge=1)


class TablaEquivalenciaUpdate(BaseModel):
    """Actualización parcial: todo opcional."""

    unidad_medida_id: uuid.UUID | None = None
    factor_conversion: int | None = Field(default=None, ge=1)

    # Columnas NOT NULL: omitirlas es válido, mandarlas como null no.
    _no_nulos = rechazar_nulos("unidad_medida_id", "factor_conversion")


class TablaEquivalenciaResponse(RespuestaBase):
    unidad_medida_id: uuid.UUID
    factor_conversion: int
