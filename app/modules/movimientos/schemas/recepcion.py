from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase, rechazar_nulos


class RecepcionCreate(BaseModel):
    # La columna del modelo es `factura_id`; el schema decía `facturacion_id`
    # y `CRUDService.crear` hace `Modelo(**valores)`: el alta reventaba con un
    # "invalid keyword argument" antes de tocar la base.
    guia_remision_id: uuid.UUID | None = None
    factura_id: uuid.UUID | None = None
    orden_compra_id: uuid.UUID | None = None
    almacen_id: uuid.UUID
    #: Opcional a propósito: registrar la recepción **es** recepcionar, así que
    #: si no llega, el servicio le pone `RECEPCIONADO`. Se admite enviarlo para
    #: no cerrarle la puerta a una recepción en otro estado (una anulada, por
    #: ejemplo), pero el caso normal no tiene que conocer el id del catálogo.
    estado_id: uuid.UUID | None = None
    fecha: date = Field(default_factory=date.today)
    observaciones: str | None = Field(min_length=1, max_length=500, default=None)


class RecepcionUpdate(BaseModel):
    """Actualización parcial: todo opcional."""

    guia_remision_id: uuid.UUID | None = None
    factura_id: uuid.UUID | None = None
    orden_compra_id: uuid.UUID | None = None
    almacen_id: uuid.UUID | None = None
    estado_id: uuid.UUID | None = None
    fecha: date | None = None
    observaciones: str | None = Field(min_length=1, max_length=500, default=None)

    # `observaciones`, `factura_id`, `guia_remision_id` y `orden_compra_id` no
    # entran: sus columnas admiten NULL, así que mandarlos en null es la forma
    # legítima de borrarlos.
    _no_nulos = rechazar_nulos("almacen_id", "estado_id", "fecha")


class RecepcionResponse(RespuestaBase):
    guia_remision_id: uuid.UUID | None = None
    factura_id: uuid.UUID | None = None
    orden_compra_id: uuid.UUID | None = None
    almacen_id: uuid.UUID
    estado_id: uuid.UUID
    fecha: date
    observaciones: str | None = None
