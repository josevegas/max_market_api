from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase, rechazar_nulos


class RecepcionDetalleCreate(BaseModel):
    #: Faltaba: sin la cabecera la línea quedaba huérfana y no había forma de
    #: listar el detalle de una recepción.
    recepcion_id: uuid.UUID
    producto_id: uuid.UUID
    unidad_medida_id: uuid.UUID
    # `ge=0` y no un `Field` pelado: sin la restricción, un -5 entraba. Se
    # admite 0 en las tres para poder dejar constancia de lo que no llegó.
    cantidad_esperada: int = Field(default=0, ge=0)
    cantidad_ingresada: int = Field(default=0, ge=0)
    cantidad_devuelta: int = Field(default=0, ge=0)
    # `Decimal("0")` y no `0`: con el int, Pydantic serializaba avisando de que
    # esperaba un decimal, y el importe es dinero.
    precio_unitario: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=12, decimal_places=2
    )
    codigo_lote: str | None = Field(default=None, min_length=1, max_length=30)


class RecepcionDetalleUpdate(BaseModel):
    """Actualización parcial: todo opcional."""

    recepcion_id: uuid.UUID | None = None
    producto_id: uuid.UUID | None = None
    unidad_medida_id: uuid.UUID | None = None
    cantidad_esperada: int | None = Field(default=None, ge=0)
    cantidad_ingresada: int | None = Field(default=None, ge=0)
    cantidad_devuelta: int | None = Field(default=None, ge=0)
    precio_unitario: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    codigo_lote: str | None = Field(default=None, min_length=1, max_length=30)

    # `codigo_lote` queda fuera: su columna admite NULL y mandarlo en null es
    # la forma de quitarle el lote a una línea.
    _no_nulos = rechazar_nulos(
        "recepcion_id",
        "producto_id",
        "unidad_medida_id",
        "cantidad_esperada",
        "cantidad_ingresada",
        "cantidad_devuelta",
        "precio_unitario",
    )


class RecepcionDetalleResponse(RespuestaBase):
    recepcion_id: uuid.UUID
    producto_id: uuid.UUID
    unidad_medida_id: uuid.UUID
    cantidad_esperada: int
    cantidad_ingresada: int
    cantidad_devuelta: int
    precio_unitario: Decimal
    codigo_lote: str | None = None
