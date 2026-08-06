from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select

from app.core.crud import CRUDService
from app.modules.productos.models.precio_producto import PrecioProducto


class PrecioProductoService(CRUDService[PrecioProducto]):
    modelo = PrecioProducto
    entidad = "Precio de producto"

    async def vigente(
        self, producto_id: UUID, en_fecha: date | None = None
    ) -> PrecioProducto | None:
        """Precio que rige para un producto en una fecha.

        Un precio sin `fecha_fin` sigue vigente; entre varios solapados gana el
        de inicio más reciente, que es el último que se cargó.
        """
        en_fecha = en_fecha or date.today()
        consulta = (
            select(PrecioProducto)
            .where(
                PrecioProducto.producto_id == producto_id,
                PrecioProducto.is_active.is_(True),
                PrecioProducto.fecha_inicio <= en_fecha,
                (PrecioProducto.fecha_fin.is_(None)),
            )
            .order_by(PrecioProducto.fecha_inicio.desc())
            .limit(1)
        )
        return (await self.db.execute(consulta)).scalar_one_or_none()
