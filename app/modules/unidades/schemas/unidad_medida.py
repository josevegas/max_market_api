from __future__ import annotations

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase, rechazar_nulos


class UnidadMedidaCreate(BaseModel):
    descripcion: str = Field(min_length=1, max_length=50)
    codigo: str = Field(min_length=1, max_length=10)
    #: Cuántas unidades mínimas vale una de esta unidad: `UND` → 1,
    #: `CAJA12` → 12. Viaja acá y no en un alta aparte contra
    #: `/tablas-equivalencia` porque una unidad sin equivalencia no sirve:
    #: `conversion.factor_de` corta con 400 al usarla en un movimiento. El
    #: servicio la escribe en la misma transacción que la unidad.
    factor_conversion: int = Field(default=1, ge=1)


class UnidadMedidaUpdate(BaseModel):
    """Actualización parcial: todo opcional."""

    descripcion: str | None = Field(default=None, min_length=1, max_length=50)
    codigo: str | None = Field(default=None, min_length=1, max_length=10)
    factor_conversion: int | None = Field(default=None, ge=1)

    # Columnas NOT NULL: omitirlas es válido, mandarlas como null no.
    _no_nulos = rechazar_nulos("descripcion", "codigo", "factor_conversion")


class UnidadMedidaResponse(RespuestaBase):
    descripcion: str
    codigo: str
    #: Nulo solo en unidades creadas antes de que el alta exigiera el factor.
    factor_conversion: int | None = None
