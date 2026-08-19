from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.shared.base import RespuestaBase, rechazar_nulos


class FacturaCreate(BaseModel):
    proveedor_id: uuid.UUID
    #: Serie y correlativo tal como vienen impresos, con sus ceros a la
    #: izquierda. Juntos identifican la factura dentro de ese proveedor.
    serie: str = Field(min_length=1, max_length=4)
    correlativo: str = Field(min_length=1, max_length=8)
    #: Opcional: el proveedor puede facturar sin guía, o varias guías juntas.
    guia_remision_id: uuid.UUID | None = None
    orden_compra_id: uuid.UUID
    # `ge=0` y no `min=0`: `min` no es una restricción de Pydantic, así que
    # quedaba como metadato del schema y no validaba nada. Un monto negativo
    # entraba sin más.
    monto_total: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    #: Arranca en cero: lo normal es que la factura se registre antes de
    #: pagarla. Se admite enviarlo para el caso de una ya cancelada.
    monto_pago: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=12, decimal_places=2
    )
    fecha_emision: date
    fecha_vencimiento: date
    #: Opcional: toda factura nace pendiente, así que si no llega el servicio
    #: le pone `PEN`.
    estado_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _coherente(self):
        # Las mismas reglas que los CHECK de la tabla: se validan acá para
        # devolver un 422 explicativo en lugar de un error de integridad.
        if self.fecha_vencimiento < self.fecha_emision:
            raise ValueError("fecha_vencimiento no puede ser anterior a fecha_emision.")
        if self.monto_pago > self.monto_total:
            raise ValueError("monto_pago no puede superar monto_total.")
        return self


class FacturaUpdate(BaseModel):
    """Actualización parcial: todo opcional."""

    proveedor_id: uuid.UUID | None = None
    serie: str | None = Field(default=None, min_length=1, max_length=4)
    correlativo: str | None = Field(default=None, min_length=1, max_length=8)
    guia_remision_id: uuid.UUID | None = None
    orden_compra_id: uuid.UUID | None = None
    monto_total: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    monto_pago: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    fecha_emision: date | None = None
    fecha_vencimiento: date | None = None
    estado_id: uuid.UUID | None = None

    # `guia_remision_id` no entra: su columna admite NULL, así que mandarlo en
    # null es la forma de desligar la factura de la guía.
    _no_nulos = rechazar_nulos(
        "proveedor_id",
        "serie",
        "correlativo",
        "orden_compra_id",
        "monto_total",
        "monto_pago",
        "fecha_emision",
        "fecha_vencimiento",
        "estado_id",
    )


class FacturaResponse(RespuestaBase):
    proveedor_id: uuid.UUID
    serie: str
    correlativo: str
    guia_remision_id: uuid.UUID | None = None
    orden_compra_id: uuid.UUID
    monto_total: Decimal
    monto_pago: Decimal
    fecha_emision: date
    fecha_vencimiento: date
    estado_id: uuid.UUID
    #: Lo que la orden comprometía. No es una columna: se resuelve al leer, y
    #: viaja para que quien revisa la factura no tenga que ir a buscarlo.
    monto_orden: Decimal | None = None
    #: `True` cuando la factura no cobra lo que la orden comprometía. No
    #: bloquea nada —entregas parciales, fletes y ajustes son legítimos—, pero
    #: quien revisa tiene que verlo sin comparar a ojo.
    difiere_de_la_orden: bool = False
