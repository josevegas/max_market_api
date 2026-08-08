"""Endpoints para asignar productos a un proveedor.

Las rutas cuelgan de la empresa (`/empresas/{id}/productos`) porque el caso de
uso es "qué distribuye este proveedor", no "gestionar una tabla intermedia".
La consulta inversa vive en `/productos/{id}/proveedores`.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.crud_router import a_http
from app.core.dependencies import get_db
from app.core.exceptions import ErrorDeDominio
from app.modules.proveedores.schemas.proveedor_producto import (
    AsignarProductosInput,
    ProductoDelProveedor,
    ProveedorDelProducto,
    ProveedorProductoResponse,
    TiempoAtencionInput,
)
from app.modules.proveedores.services.proveedor_producto_service import (
    ProveedorProductoService,
)

router = APIRouter(tags=["Productos del proveedor"])


@router.get(
    "/empresas/{empresa_id}/productos",
    response_model=list[ProductoDelProveedor],
    summary="Productos que distribuye un proveedor",
    description="Ordenados por tiempo de atención: primero lo que llega antes.",
)
async def productos_del_proveedor(empresa_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        return await ProveedorProductoService(db).productos_de(empresa_id)
    except ErrorDeDominio as e:
        raise a_http(e)


@router.put(
    "/empresas/{empresa_id}/productos/{producto_id}",
    response_model=ProveedorProductoResponse,
    summary="Asignar un producto a un proveedor",
    description=(
        "PUT y no POST porque es idempotente: si el proveedor ya distribuía el "
        "producto, se actualiza su tiempo de atención en lugar de fallar."
    ),
)
async def asignar_producto(
    empresa_id: UUID,
    producto_id: UUID,
    datos: TiempoAtencionInput,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await ProveedorProductoService(db).asignar(
            empresa_id, producto_id, datos.tiempo_atencion
        )
    except ErrorDeDominio as e:
        raise a_http(e)


@router.post(
    "/empresas/{empresa_id}/productos",
    response_model=list[ProveedorProductoResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Asignar varios productos de una vez",
    description=(
        "Carga masiva del catálogo de un proveedor. Si algún producto no "
        "existe, no se guarda ninguna: la carga no queda a medias."
    ),
)
async def asignar_productos(
    empresa_id: UUID,
    datos: AsignarProductosInput,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await ProveedorProductoService(db).asignar_varios(
            empresa_id, datos.asignaciones
        )
    except ErrorDeDominio as e:
        raise a_http(e)


@router.delete(
    "/empresas/{empresa_id}/productos/{producto_id}",
    response_model=ProveedorProductoResponse,
    summary="Quitar un producto del catálogo del proveedor",
    description=(
        "Baja lógica: la fila se conserva porque una orden de compra histórica "
        "puede referirse a ella."
    ),
)
async def quitar_producto(
    empresa_id: UUID, producto_id: UUID, db: AsyncSession = Depends(get_db)
):
    try:
        return await ProveedorProductoService(db).quitar(empresa_id, producto_id)
    except ErrorDeDominio as e:
        raise a_http(e)


@router.get(
    "/productos/{producto_id}/proveedores",
    response_model=list[ProveedorDelProducto],
    summary="Proveedores de un producto",
    description=(
        "Del más rápido al más lento. Es la consulta que hace Compras antes de "
        "emitir una orden."
    ),
)
async def proveedores_del_producto(
    producto_id: UUID, db: AsyncSession = Depends(get_db)
):
    try:
        return await ProveedorProductoService(db).proveedores_de(producto_id)
    except ErrorDeDominio as e:
        raise a_http(e)


@router.get(
    "/productos/{producto_id}/proveedor-mas-rapido",
    response_model=ProveedorDelProducto | None,
    summary="Proveedor con menor tiempo de atención",
)
async def proveedor_mas_rapido(producto_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        return await ProveedorProductoService(db).proveedor_mas_rapido(producto_id)
    except ErrorDeDominio as e:
        raise a_http(e)
