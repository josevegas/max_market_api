"""Conversión de cantidades a la unidad mínima.

El almacén guarda todo en la unidad mínima, mientras que los documentos de
compra vienen por paquetes: una guía de 4 cajas y un lote de 48 unidades
pueden ser lo mismo. Comparar los números en crudo daría por bueno cualquier
descuadre, así que antes de compararlos se llevan los dos al mismo terreno.

`tabla_equivalencia.factor_conversion` es cuántas unidades mínimas vale una de
esa unidad: `UND` → 1, `CAJA12` → 12. El factor es global por unidad, así que
el catálogo distingue el empaque (`CAJA12` y `CAJA24` son unidades distintas).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictoError, ReferenciaInvalidaError
from app.modules.unidades.models.tabla_equivalencia import TablaEquivalencia
from app.modules.unidades.models.unidad_medida import UnidadMedida


async def factor_de(db: AsyncSession, unidad_medida_id: UUID) -> int:
    """Unidades mínimas que vale una unidad de `unidad_medida_id`.

    Si no hay equivalencia registrada se corta con un 400 en vez de asumir 1:
    ese supuesto daría por buena una guía de 4 cajas contra 4 unidades sueltas,
    y el descuadre no aparecería hasta un inventario.
    """
    factor = await db.scalar(
        select(TablaEquivalencia.factor_conversion).where(
            TablaEquivalencia.unidad_medida_id == unidad_medida_id,
            TablaEquivalencia.is_active.is_(True),
        )
    )
    if factor is None:
        codigo = await db.scalar(
            select(UnidadMedida.codigo).where(UnidadMedida.id == unidad_medida_id)
        )
        raise ReferenciaInvalidaError(
            f"No hay equivalencia registrada para la unidad "
            f"{codigo or unidad_medida_id}: no se puede convertir a la unidad "
            "mínima. Regístrela en la tabla de equivalencias."
        )
    return factor


async def a_unidades_minimas(
    db: AsyncSession, cantidad: int, unidad_medida_id: UUID
) -> int:
    """`cantidad` expresada en la unidad mínima."""
    return cantidad * await factor_de(db, unidad_medida_id)


async def a_unidad(
    db: AsyncSession, cantidad: int, desde_id: UUID, hasta_id: UUID
) -> int:
    """`cantidad` reexpresada en otra unidad, pasando por la mínima.

    Corta si la conversión no da exacta: 5 unidades sueltas no son "media caja
    de 12", y redondear haría aparecer o desaparecer mercadería en silencio,
    que es justo lo que el resto del módulo se ocupa de impedir.
    """
    if desde_id == hasta_id:
        return cantidad

    minimas = await a_unidades_minimas(db, cantidad, desde_id)
    factor = await factor_de(db, hasta_id)
    if minimas % factor:
        raise ConflictoError(
            f"{cantidad} no se puede expresar en la unidad de destino: son "
            f"{minimas} unidades mínimas y esa unidad vale {factor}. Ajuste la "
            "cantidad o registre el movimiento en otra unidad."
        )
    return minimas // factor
