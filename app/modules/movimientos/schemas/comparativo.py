from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel


class CriterioResponse(BaseModel):
    """Un criterio ya evaluado para una cotización."""

    #: El valor crudo, en su propia unidad: soles por unidad mínima para
    #: `precio`, días para `entrega` y `pago`, por ciento para `stock`. Va aparte
    #: del puntaje porque la pantalla muestra los dos: el número real es lo que
    #: el usuario reconoce del documento, y el puntaje es lo que lo compara.
    valor: Decimal | None = None
    #: 0 a 100, contra el mejor valor del grupo.
    puntaje: Decimal
    #: Lo que aporta al total: `puntaje * peso / 100`.
    aporte: Decimal


class CotizacionEvaluadaResponse(BaseModel):
    cotizacion_id: uuid.UUID
    proveedor_id: uuid.UUID
    proveedor: str
    estado_id: uuid.UUID
    estado: str
    #: Lo que dice el documento, para que la pantalla no muestre solo el número
    #: normalizado: es lo que se puede cotejar contra la cotización impresa.
    monto_total: Decimal
    tiempo_atencion: int
    condicion_pago_dias: int
    #: Unidades mínimas del pedido que cubre.
    unidades_atendidas: int
    #: Soles por unidad mínima atendida, que es con lo que se puntúa el precio.
    #: `None` si no atiende nada: no tener precio no es tener precio cero.
    precio_por_unidad: Decimal | None = None
    #: Qué porcentaje del pedido cubre, de 0 a 100.
    cobertura: Decimal
    #: Productos del pedido que esta cotización no cotiza. Es la explicación de
    #: una cobertura baja; sin ellos el porcentaje no dice qué falta.
    productos_sin_cotizar: list[uuid.UUID] = []
    #: Indexado por `precio`, `entrega`, `stock` y `pago`.
    criterios: dict[str, CriterioResponse]
    puntaje_total: Decimal
    #: `True` en la de mayor puntaje. Si hay empate exacto lo llevan todas las
    #: empatadas, porque el comparativo no las distingue.
    optimo: bool


class ComparativoResponse(BaseModel):
    """El cuadro de decisión completo."""

    pedido_id: uuid.UUID
    requerimiento_id: uuid.UUID
    #: Unidades mínimas que pide el pedido: el denominador de la cobertura.
    unidades_pedidas: int
    #: Los pesos con los que se calculó, para que la pantalla los rotule sin
    #: tener que repetirlos y quedar desincronizada si cambian.
    pesos: dict[str, int]
    #: De mayor a menor puntaje. Entran también las rechazadas —el cuadro es el
    #: registro de contra qué se eligió al proveedor, y aprobar una rechaza a las
    #: demás— pero una rechazada nunca viene con `optimo` en `true`.
    cotizaciones: list[CotizacionEvaluadaResponse]
