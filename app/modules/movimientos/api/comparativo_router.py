"""Comparativo de cotizaciones, para decidir cuál aprobar.

Dos entradas al mismo cuadro. La del pedido es la natural —las cotizaciones
cuelgan del pedido— y la del requerimiento es la que pide el usuario, que piensa
en términos de lo que se necesitaba, no del documento intermedio. Un
requerimiento genera un solo pedido, así que el salto es unívoco.

No hay endpoint para "aprobar la del comparativo": aprobar una cotización es
`PATCH /cotizaciones/{id}` con el estado, lo mismo que desde su formulario. Un
atajo aquí sería una segunda puerta a la misma regla, y la generación de la orden
de compra al aprobar vive en `GeneraSucesorAlAprobar`, no en la pantalla.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.crud_router import a_http
from app.core.dependencies import get_db
from app.core.exceptions import ErrorDeDominio
from app.modules.movimientos.schemas.comparativo import ComparativoResponse
from app.modules.movimientos.services.comparativo_service import (
    comparar_cotizaciones,
    comparativo_de_requerimiento,
)

router = APIRouter(tags=["Comparativo de cotizaciones"])

_DESCRIPCION = (
    "Puntúa las cotizaciones con cuatro criterios pesados —precio 35%, entrega "
    "25%, stock atendido 20%, condición de pago 20%— y marca como `optimo` la "
    "de mayor puntaje. El precio se mide **por unidad atendida** y no por monto "
    "total: cada cotización cubre los productos que su proveedor distribuye, así "
    "que comparar montos premiaría a quien cotiza menos. Las rechazadas se listan "
    "pero nunca salen como `optimo`. La decisión sigue siendo del usuario: el "
    "óptimo es una sugerencia, y se puede aprobar cualquiera —al hacerlo, las "
    "demás cotizaciones del pedido quedan rechazadas."
)


@router.get(
    "/pedidos/{pedido_id}/comparativo-cotizaciones",
    response_model=ComparativoResponse,
    summary="Comparativo de las cotizaciones de un pedido",
    description=_DESCRIPCION,
)
async def comparativo_del_pedido(pedido_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        return await comparar_cotizaciones(db, pedido_id)
    except ErrorDeDominio as e:
        raise a_http(e)


@router.get(
    "/requerimientos/{requerimiento_id}/comparativo-cotizaciones",
    response_model=ComparativoResponse,
    summary="Comparativo de las cotizaciones de un requerimiento",
    description=(
        f"{_DESCRIPCION}\n\nEntra por el requerimiento y resuelve el pedido que "
        "generó. Devuelve 400 si todavía no generó ninguno: sin pedido no hay "
        "cotizaciones que comparar."
    ),
)
async def comparativo_del_requerimiento(
    requerimiento_id: UUID, db: AsyncSession = Depends(get_db)
):
    try:
        return await comparativo_de_requerimiento(db, requerimiento_id)
    except ErrorDeDominio as e:
        raise a_http(e)
