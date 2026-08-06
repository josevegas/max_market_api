"""Router raíz de la v1: acá se cuelga cada módulo."""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.productos.api.categoria_router import router as categorias_router
from app.modules.productos.api.familia_router import router as familias_router
from app.modules.productos.api.precio_producto_router import router as precios_router
from app.modules.productos.api.presentacion_router import (
    router as presentaciones_router,
)
from app.modules.productos.api.producto_router import router as productos_router
from app.modules.productos.api.sub_categoria_router import (
    router as sub_categorias_router,
)
from app.modules.productos.api.sub_familia_router import router as sub_familias_router

api_router = APIRouter()

# Catálogo, de lo general a lo particular.
api_router.include_router(familias_router)
api_router.include_router(sub_familias_router)
api_router.include_router(categorias_router)
api_router.include_router(sub_categorias_router)
api_router.include_router(presentaciones_router)
api_router.include_router(productos_router)
api_router.include_router(precios_router)
