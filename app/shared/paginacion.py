"""Envoltorio de los listados.

Un array pelado no dice cuántos registros hay en total, así que un cliente que
recibe 100 filas no puede distinguir «esto es todo» de «esto es la primera
página». El resultado era que la interfaz pedía `limite=500` por si acaso y aun
así truncaba en silencio al pasar de ahí.

Con `total` el cliente sabe cuántas páginas hay y puede pedir solo la que se ve.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")

#: Valores por defecto del troceado, compartidos por la fábrica de routers y
#: por los listados a medida para que todos se comporten igual.
LIMITE_POR_DEFECTO = 50
LIMITE_MAXIMO = 500


class Pagina(BaseModel, Generic[T]):
    """Un tramo de un listado, con el tamaño del conjunto completo."""

    items: list[T]
    #: Registros que cumplen el filtro, ignorando `limite` y `desplazamiento`.
    total: int
    limite: int
    desplazamiento: int
