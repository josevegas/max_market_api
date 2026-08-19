from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase, rechazar_nulos


class TipoComprobanteCreate(BaseModel):
    descripcion: str = Field(min_length=1, max_length=25)
    codigo: str = Field(min_length=1, max_length=10)


class TipoComprobanteUpdate(BaseModel):
    """Actualización parcial: todo opcional."""

    descripcion: str | None = Field(default=None, min_length=1, max_length=25)
    codigo: str | None = Field(default=None, min_length=1, max_length=10)

    _no_nulos = rechazar_nulos("descripcion", "codigo")


class TipoComprobanteResponse(RespuestaBase):
    descripcion: str
    codigo: str


class VentaCreate(BaseModel):
    #: De qué almacén sale la mercadería: es donde están los lotes que se
    #: descuentan y la ficha que fija el precio.
    almacen_id: uuid.UUID
    tipo_comprobante_id: uuid.UUID
    serie_comprobante: str = Field(min_length=1, max_length=4)
    numero_comprobante: str = Field(min_length=1, max_length=8)
    fecha: date = Field(default_factory=date.today)
    #: Solo la factura lo exige. El servicio lo comprueba contra el tipo de
    #: comprobante, que es quien sabe cuál es cuál.
    ruc_cliente: str | None = Field(default=None, min_length=11, max_length=11)
    #: Opcional: toda venta nace pendiente, así que si no llega el servicio le
    #: pone `PEN`.
    estado_id: uuid.UUID | None = None
    # `monto_total` no se envía: lo suman las líneas.


class VentaUpdate(BaseModel):
    """Actualización parcial: todo opcional."""

    almacen_id: uuid.UUID | None = None
    tipo_comprobante_id: uuid.UUID | None = None
    serie_comprobante: str | None = Field(default=None, min_length=1, max_length=4)
    numero_comprobante: str | None = Field(default=None, min_length=1, max_length=8)
    fecha: date | None = None
    ruc_cliente: str | None = Field(default=None, min_length=11, max_length=11)
    estado_id: uuid.UUID | None = None

    # `ruc_cliente` no entra: su columna admite NULL, así que mandarlo en null
    # es la forma de quitarlo de una boleta.
    _no_nulos = rechazar_nulos(
        "almacen_id",
        "tipo_comprobante_id",
        "serie_comprobante",
        "numero_comprobante",
        "fecha",
        "estado_id",
    )


class VentaResponse(RespuestaBase):
    almacen_id: uuid.UUID
    tipo_comprobante_id: uuid.UUID
    serie_comprobante: str
    numero_comprobante: str
    fecha: date
    monto_total: Decimal
    ruc_cliente: str | None = None
    estado_id: uuid.UUID


class VentaDetalleCreate(BaseModel):
    venta_id: uuid.UUID
    producto_id: uuid.UUID
    #: En la unidad de venta del producto, la misma en que están los lotes.
    cantidad: int = Field(gt=0)
    # Ni `precio_unitario` (sale de la ficha del almacén) ni `monto` (lo deriva
    # el servicio): mandarlos se ignora.


class VentaDetalleUpdate(BaseModel):
    """Actualización parcial: todo opcional."""

    cantidad: int | None = Field(default=None, gt=0)

    _no_nulos = rechazar_nulos("cantidad")


class VentaDetalleResponse(RespuestaBase):
    venta_id: uuid.UUID
    producto_id: uuid.UUID
    cantidad: int
    precio_unitario: Decimal
    monto: Decimal
