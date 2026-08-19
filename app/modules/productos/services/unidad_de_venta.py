"""En qué unidad se mueve un producto dentro del market.

Vive con el producto y no con el lote ni con el stock porque es un hecho del
producto, y porque los dos lo necesitan: el lote guarda su cantidad en esta
unidad y el stock la usa para comparar. Tenerlo en cualquiera de los dos
obligaba al otro a importarlo, y con eso el ciclo de imports estaba servido.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ReferenciaInvalidaError
from app.modules.productos.models.producto import Producto


async def unidad_venta_de(db: AsyncSession, producto_id: UUID) -> UUID:
    """Unidad en la que se expresan los lotes de ese producto."""
    unidad = await db.scalar(
        select(Producto.unidad_venta).where(Producto.id == producto_id)
    )
    if unidad is None:
        raise ReferenciaInvalidaError(
            f"No existe el producto {producto_id}: sin él no se sabe en qué "
            "unidad está el lote."
        )
    return unidad
