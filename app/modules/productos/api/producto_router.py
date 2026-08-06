from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.crud_router import a_http, crear_router_crud
from app.core.dependencies import get_db
from app.core.exceptions import NoEncontradoError
from app.modules.productos.schemas.precio_producto import PrecioProductoResponse
from app.modules.productos.schemas.producto import (
    ProductoCreate,
    ProductoResponse,
    ProductoUpdate,
)
from app.modules.productos.services.precio_producto_service import PrecioProductoService
from app.modules.productos.services.producto_service import ProductoService

router = crear_router_crud(
    prefijo="/productos",
    etiqueta="Productos",
    servicio=ProductoService,
    schema_create=ProductoCreate,
    schema_update=ProductoUpdate,
    schema_response=ProductoResponse,
    filtros={
        "familia_id": UUID,
        "sub_familia_id": UUID,
        "categoria_id": UUID,
        "sub_categoria_id": UUID,
        "presentacion_id": UUID,
    },
)


# ── Endpoints propios de productos ──────────────────────────────────────────
# Van declarados con rutas literales antes que `/{registro_id}` no haría falta
# (FastAPI resuelve por orden de registro y el CRUD ya está montado), por eso
# se usan prefijos que no colisionan con un UUID.


@router.get(
    "/sku/{sku}",
    response_model=ProductoResponse,
    summary="Obtener producto por SKU",
    description="El SKU es el identificador con el que opera el negocio.",
)
async def obtener_por_sku(sku: str, db: AsyncSession = Depends(get_db)):
    try:
        return await ProductoService(db).obtener_por_sku(sku)
    except NoEncontradoError as e:
        raise a_http(e)


@router.get(
    "/{producto_id}/precios",
    response_model=list[PrecioProductoResponse],
    summary="Historial de precios del producto",
)
async def precios_del_producto(producto_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        await ProductoService(db).obtener(producto_id)  # 404 si no existe
    except NoEncontradoError as e:
        raise a_http(e)
    return await PrecioProductoService(db).listar(
        solo_activos=False, filtros={"producto_id": producto_id}, limite=500
    )


@router.get(
    "/{producto_id}/precio-vigente",
    response_model=PrecioProductoResponse,
    summary="Precio vigente hoy",
)
async def precio_vigente(producto_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        await ProductoService(db).obtener(producto_id)
    except NoEncontradoError as e:
        raise a_http(e)
    precio = await PrecioProductoService(db).vigente(producto_id)
    if precio is None:
        raise HTTPException(status_code=404, detail="El producto no tiene precio vigente.")
    return precio
