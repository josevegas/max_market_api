"""Registro central de modelos.

Alembic solo detecta lo que esté cargado en `Base.metadata`, y los modelos se
registran al importarse. Cada modelo nuevo se agrega acá; si no, `--autogenerate`
lo ignora en silencio y, peor, propone borrar sus tablas.
"""

from __future__ import annotations

from app.db.base import Base
from app.modules.bancos.models.banco import Banco
from app.modules.bancos.models.cuenta import Cuenta
from app.modules.bancos.models.tipo_cuenta import TipoCuenta
from app.modules.productos.models.categoria import Categoria
from app.modules.productos.models.familia import Familia
from app.modules.productos.models.precio_producto import PrecioProducto
from app.modules.productos.models.presentacion import Presentacion
from app.modules.productos.models.producto import Producto
from app.modules.productos.models.sub_categoria import SubCategoria
from app.modules.productos.models.sub_familia import SubFamilia
from app.modules.proveedores.models.empresa import Empresa
from app.modules.proveedores.models.proveedor_producto import ProveedorProducto

__all__ = [
    "Banco",
    "Base",
    "Categoria",
    "Cuenta",
    "Empresa",
    "Familia",
    "PrecioProducto",
    "Presentacion",
    "Producto",
    "ProveedorProducto",
    "SubCategoria",
    "SubFamilia",
    "TipoCuenta",
]
