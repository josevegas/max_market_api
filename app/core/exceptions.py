"""Errores de dominio.

Los servicios levantan estos; los routers los traducen a HTTP. Así la lógica de
negocio no depende de FastAPI y se puede probar sin levantar la API.
"""

from __future__ import annotations


class ErrorDeDominio(Exception):
    """Base de los errores previsibles del negocio."""


class NoEncontradoError(ErrorDeDominio):
    """No existe el recurso pedido. → 404"""

    def __init__(self, entidad: str, identificador: object) -> None:
        super().__init__(f"{entidad} {identificador} no encontrado.")
        self.entidad = entidad
        self.identificador = identificador


class ConflictoError(ErrorDeDominio):
    """La operación choca con una regla o con datos existentes. → 409"""


class ReferenciaInvalidaError(ErrorDeDominio):
    """Se referencia algo que no existe o que no se puede usar. → 400"""
