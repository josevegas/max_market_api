"""El precio de venta sale del de compra, no se teclea.

    precio_venta = (precio_compra / IGV * (1 + margen/100) + monto_POS) * IGV

El precio de compra viene **con IGV** —es lo que factura el proveedor—, así que
primero se le saca para trabajar sobre el valor, se le aplica el margen de la
categoría del producto, se le suma el recargo de punto de venta y recién ahí se
vuelve a gravar. El `monto_POS` entra antes del IGV a propósito: también
tributa.

El margen vive en la categoría (`categoria.margen_ganancia`) y es un
**porcentaje**: 18.50 significa 18.5%. Hasta acá era un dato que se guardaba y
nadie usaba; el precio de venta se cargaba a mano y nada obligaba a que
respetara el margen que la categoría declaraba.

`IGV` y `monto_POS` salen de la configuración y no del código: la tasa cambia
por ley y el recargo es una decisión comercial de cada instalación.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ReferenciaInvalidaError
from app.modules.productos.models.categoria import Categoria
from app.modules.productos.models.producto import Producto

#: Los importes se guardan con dos decimales (`Numeric(12, 2)`).
_CENTIMOS = Decimal("0.01")
_CIEN = Decimal("100")


def precio_de_venta(
    precio_compra: Decimal,
    margen_ganancia: Decimal,
    igv: Decimal,
    monto_pos: Decimal,
) -> Decimal:
    """La fórmula, sin base de datos de por medio.

    Se redondea **una sola vez, al final**: redondear cada paso arrastraría el
    error hasta el precio, y con `ROUND_HALF_UP` porque es como se redondea el
    dinero acá, no con el "al par" que trae Python por defecto.
    """
    valor = precio_compra / igv
    con_margen = valor * (Decimal(1) + margen_ganancia / _CIEN)
    return ((con_margen + monto_pos) * igv).quantize(_CENTIMOS, rounding=ROUND_HALF_UP)


async def margen_del_producto(db: AsyncSession, producto_id: UUID) -> Decimal:
    """El margen de la categoría a la que pertenece el producto."""
    margen = await db.scalar(
        select(Categoria.margen_ganancia)
        .join(Producto, Producto.categoria_id == Categoria.id)
        .where(Producto.id == producto_id)
    )
    if margen is None:
        raise ReferenciaInvalidaError(
            f"No se encontró la categoría del producto {producto_id}: sin su "
            "margen de ganancia no se puede calcular el precio de venta."
        )
    return margen


async def calcular_precio_venta(
    db: AsyncSession, producto_id: UUID, precio_compra: Decimal
) -> Decimal:
    """El precio de venta de ese producto para ese precio de compra."""
    ajustes = get_settings()
    return precio_de_venta(
        precio_compra,
        await margen_del_producto(db, producto_id),
        ajustes.IGV,
        ajustes.MONTO_POS,
    )
