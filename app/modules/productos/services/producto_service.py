from __future__ import annotations

from sqlalchemy import select

from app.core.crud import CRUDService
from app.core.exceptions import NoEncontradoError
from app.modules.productos.models.producto import Producto


class ProductoService(CRUDService[Producto]):
    modelo = Producto
    entidad = "Producto"

    async def obtener_por_sku(self, sku: str) -> Producto:
        """El SKU es el identificador con el que trabaja el negocio, así que
        se puede buscar por él sin conocer el UUID."""
        producto = (
            await self.db.execute(select(Producto).where(Producto.sku == sku))
        ).scalar_one_or_none()
        if producto is None:
            raise NoEncontradoError(self.entidad, sku)
        return producto
