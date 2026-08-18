"""Piezas comunes a los schemas de todos los módulos."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


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


def rechazar_nulos(*campos: str):
    """Validador para los `*Update` cuyas columnas son NOT NULL.

    En un PATCH hay dos cosas distintas que el tipo `str | None` confunde:
    **omitir** el campo (dejarlo como está) y **enviarlo como null** (borrarlo).
    Lo primero es válido; lo segundo choca contra el NOT NULL de la columna y
    sale como un 400 genérico de integridad, sin decir qué campo fue.

    Con esto el segundo caso se corta en la validación y el cliente recibe un
    422 que nombra el campo. Funciona porque Pydantic no valida los valores por
    defecto: el validador solo corre cuando el campo llegó en la petición.

    Uso:

        class ZonaUpdate(BaseModel):
            nombre: str | None = None
            _no_nulos = rechazar_nulos("nombre")
    """

    def _validar(v: Any) -> Any:
        if v is None:
            raise ValueError("no admite null; omita el campo para dejarlo sin cambios")
        return v

    return field_validator(*campos)(_validar)
