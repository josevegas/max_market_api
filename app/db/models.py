"""Registro central de modelos.

Alembic solo detecta lo que esté cargado en `Base.metadata`, y los modelos se
registran al importarse. Cada modelo nuevo se agrega acá; si no, `--autogenerate`
lo ignora en silencio y, peor, propone borrar sus tablas.
"""

from __future__ import annotations

from app.db.base import Base
from app.modules.almacenes.models.almacen import Almacen
from app.modules.almacenes.models.producto_almacen import ProductoAlmacen
from app.modules.almacenes.models.producto_lote import ProductoLote
from app.modules.bancos.models.banco import Banco
from app.modules.bancos.models.cuenta import Cuenta
from app.modules.bancos.models.tipo_cuenta import TipoCuenta
from app.modules.markets.models.market import Market
from app.modules.markets.models.sede import Sede
from app.modules.markets.models.zona import Zona
from app.modules.movimientos.models.cotizacion import Cotizacion
from app.modules.movimientos.models.cotizacion_detalle import CotizacionDetalle
from app.modules.movimientos.models.estado import Estado
from app.modules.movimientos.models.guia_remision import GuiaRemision
from app.modules.movimientos.models.guia_remision_detalle import (
    GuiaRemisionDetalle,
)
from app.modules.movimientos.models.orden_compra import OrdenCompra
from app.modules.movimientos.models.orden_compra_detalle import (
    OrdenCompraDetalle,
)
from app.modules.movimientos.models.pedido import Pedido
from app.modules.movimientos.models.pedido_detalle import PedidoDetalle
from app.modules.movimientos.models.recepcion import Recepcion
from app.modules.movimientos.models.recepcion_detalle import RecepcionDetalle
from app.modules.movimientos.models.requerimiento import Requerimiento
from app.modules.movimientos.models.requerimiento_detalle import (
    RequerimientoDetalle,
)
from app.modules.productos.models.categoria import Categoria
from app.modules.productos.models.familia import Familia
from app.modules.productos.models.precio_producto import PrecioProducto
from app.modules.productos.models.presentacion import Presentacion
from app.modules.productos.models.producto import Producto
from app.modules.productos.models.sub_categoria import SubCategoria
from app.modules.productos.models.sub_familia import SubFamilia
from app.modules.proveedores.models.empresa import Empresa
from app.modules.proveedores.models.padron_agente import (
    PadronAgente,
    PadronSincronizacion,
)
from app.modules.proveedores.models.proveedor_producto import ProveedorProducto
from app.modules.unidades.models.tabla_equivalencia import TablaEquivalencia
from app.modules.unidades.models.unidad_medida import UnidadMedida

__all__ = [
    "Almacen",
    "Banco",
    "Base",
    "Categoria",
    "Cotizacion",
    "CotizacionDetalle",
    "Cuenta",
    "Empresa",
    "Estado",
    "Familia",
    "GuiaRemision",
    "GuiaRemisionDetalle",
    "Market",
    "OrdenCompra",
    "OrdenCompraDetalle",
    "PadronAgente",
    "PadronSincronizacion",
    "Pedido",
    "PedidoDetalle",
    "PrecioProducto",
    "Presentacion",
    "Producto",
    "ProductoAlmacen",
    "ProductoLote",
    "ProveedorProducto",
    "Recepcion",
    "RecepcionDetalle",
    "Requerimiento",
    "RequerimientoDetalle",
    "Sede",
    "SubCategoria",
    "SubFamilia",
    "TablaEquivalencia",
    "TipoCuenta",
    "UnidadMedida",
    "Zona",
]
