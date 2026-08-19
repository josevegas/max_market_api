"""Consulta del stock de un almacén.

Cuelga de `/almacenes/{id}/stock` y no de un recurso propio porque el stock no
es una tabla: es lo que suman los lotes de ese almacén. Preguntar "cuánto hay"
es preguntarle al almacén, no listar una entidad.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.crud_router import a_http
from app.core.dependencies import get_db
from app.core.exceptions import ErrorDeDominio
from app.modules.almacenes.schemas.stock import StockDeProductoResponse
from app.modules.almacenes.services.almacen_service import AlmacenService
from app.modules.almacenes.services.stock_service import stock_del_almacen

router = APIRouter(tags=["Stock"])


@router.get(
    "/almacenes/{almacen_id}/stock",
    response_model=list[StockDeProductoResponse],
    summary="Stock disponible del almacén",
    description=(
        "Lo que suman los lotes disponibles de cada producto, con el mínimo y "
        "el máximo de su ficha. Con `bajo_minimo=true` devuelve solo lo que "
        "hay que reponer."
    ),
)
async def stock(
    almacen_id: UUID,
    bajo_minimo: bool = Query(
        False, description="Solo los productos por debajo de su stock mínimo."
    ),
    db: AsyncSession = Depends(get_db),
):
    try:
        # Un almacén que no existe es un 404, no una lista vacía: son cosas
        # distintas y el cliente no puede distinguirlas por el resultado.
        await AlmacenService(db).obtener(almacen_id)
        return await stock_del_almacen(db, almacen_id, bajo_minimo)
    except ErrorDeDominio as e:
        raise a_http(e)
