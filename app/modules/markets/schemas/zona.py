from __future__ import annotations

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase, rechazar_nulos


class ZonaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=50)
    codigo: str = Field(min_length=1, max_length=10)


class ZonaUpdate(BaseModel):
    """Actualización parcial: todo opcional.

    Los `= None` son obligatorios. Sin ellos Pydantic trata el campo como
    obligatorio-que-admite-null: un PATCH que no lo enviara sería rechazado, y
    uno que enviara `null` intentaría dejar en NULL una columna que no lo
    admite.
    """

    nombre: str | None = Field(default=None, min_length=1, max_length=50)
    codigo: str | None = Field(default=None, min_length=1, max_length=10)

    # Columnas NOT NULL: omitirlas es válido, mandarlas como null no.
    _no_nulos = rechazar_nulos("nombre", "codigo")


class ZonaResponse(RespuestaBase):
    nombre: str
    codigo: str
