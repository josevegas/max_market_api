"""Router raíz de la v1: acá se cuelga cada módulo."""

from __future__ import annotations

from fastapi import APIRouter

api_router = APIRouter()

# Los módulos de dominio (productos, usuarios) se agregan acá a medida que
# tengan endpoints:
#
#     from app.modules.productos.api.producto_router import router as productos_router
#     api_router.include_router(productos_router)
