"""Router raíz de la v1: acá se cuelga cada módulo."""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.almacenes.api.almacen_router import router as almacenes_router
from app.modules.almacenes.api.producto_almacen_router import (
    router as productos_almacen_router,
)
from app.modules.almacenes.api.producto_lote_router import (
    router as productos_lote_router,
)
from app.modules.bancos.api.banco_router import router as bancos_router
from app.modules.bancos.api.cuenta_router import router as cuentas_router
from app.modules.bancos.api.tipo_cuenta_router import router as tipos_cuenta_router
from app.modules.markets.api.market_router import router as markets_router
from app.modules.markets.api.sede_router import router as sedes_router
from app.modules.markets.api.zona_router import router as zonas_router
from app.modules.movimientos.api.cotizacion_detalle_router import (
    router as cotizaciones_detalle_router,
)
from app.modules.movimientos.api.cotizacion_router import router as cotizaciones_router
from app.modules.movimientos.api.estado_router import router as estados_router
from app.modules.movimientos.api.guia_remision_detalle_router import (
    router as guias_remision_detalle_router,
)
from app.modules.movimientos.api.guia_remision_router import (
    router as guias_remision_router,
)
from app.modules.movimientos.api.orden_compra_detalle_router import (
    router as ordenes_compra_detalle_router,
)
from app.modules.movimientos.api.orden_compra_router import (
    router as ordenes_compra_router,
)
from app.modules.movimientos.api.pedido_detalle_router import (
    router as pedidos_detalle_router,
)
from app.modules.movimientos.api.pedido_router import router as pedidos_router
from app.modules.movimientos.api.recepcion_detalle_router import (
    router as recepciones_detalle_router,
)
from app.modules.movimientos.api.recepcion_router import router as recepciones_router
from app.modules.movimientos.api.requerimiento_detalle_router import (
    router as requerimientos_detalle_router,
)
from app.modules.movimientos.api.requerimiento_router import (
    router as requerimientos_router,
)
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
from app.modules.proveedores.api.empresa_router import router as empresas_router
from app.modules.proveedores.api.padron_router import router as padron_router
from app.modules.proveedores.api.proveedor_producto_router import (
    router as proveedor_productos_router,
)
from app.modules.unidades.api.tabla_equivalencia_router import (
    router as tablas_equivalencia_router,
)
from app.modules.unidades.api.unidad_medida_router import (
    router as unidades_medida_router,
)

api_router = APIRouter()

# Catálogo, de lo general a lo particular.
api_router.include_router(familias_router)
api_router.include_router(sub_familias_router)
api_router.include_router(categorias_router)
api_router.include_router(sub_categorias_router)
api_router.include_router(presentaciones_router)
api_router.include_router(productos_router)
api_router.include_router(precios_router)
api_router.include_router(empresas_router)
api_router.include_router(proveedor_productos_router)
api_router.include_router(padron_router)

# Estructura comercial, de lo general a lo particular: zona → sede → market.
api_router.include_router(zonas_router)
api_router.include_router(sedes_router)
api_router.include_router(markets_router)

# Bancos y cuentas.
api_router.include_router(bancos_router)
api_router.include_router(tipos_cuenta_router)
api_router.include_router(cuentas_router)

# Unidades de medida: las necesita la ficha de producto en almacén.
api_router.include_router(unidades_medida_router)
api_router.include_router(tablas_equivalencia_router)

# Almacenes y su stock.
api_router.include_router(almacenes_router)
api_router.include_router(productos_almacen_router)
api_router.include_router(productos_lote_router)

# Compras, en el orden en que ocurren: requerimiento → pedido → cotización →
# orden de compra → guía de remisión → recepción.
api_router.include_router(estados_router)
api_router.include_router(requerimientos_router)
api_router.include_router(requerimientos_detalle_router)
api_router.include_router(pedidos_router)
api_router.include_router(pedidos_detalle_router)
api_router.include_router(cotizaciones_router)
api_router.include_router(cotizaciones_detalle_router)
api_router.include_router(ordenes_compra_router)
api_router.include_router(ordenes_compra_detalle_router)
api_router.include_router(guias_remision_router)
api_router.include_router(guias_remision_detalle_router)
api_router.include_router(recepciones_router)
api_router.include_router(recepciones_detalle_router)
