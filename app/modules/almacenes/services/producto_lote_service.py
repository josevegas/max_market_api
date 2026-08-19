"""Lotes recibidos, cuadrados contra lo que declara la guía de remisión.

Un lote es el bulto físico (con su código y su vencimiento); la línea de la
guía es lo que el documento dice que llegó. Una línea puede partirse en varios
lotes —vencimientos distintos, por ejemplo—, pero la suma de esos lotes no
puede superar lo declarado: si lo hiciera, el almacén acabaría con más stock
del que respalda el documento y el descuadre no aparecería hasta un inventario.

El lote no lleva unidad propia: su cantidad va siempre en la **unidad de venta
del producto**, que es en la que el market mueve el stock. La guía viene en la
unidad de compra, así que los dos lados se llevan a unidad mínima antes de
compararlos. Se compara ahí y no en unidad de venta porque el factor es entero:
convertir compra → venta directamente truncaría cuando uno no es múltiplo del
otro, y el tope quedaría por debajo de lo que la guía declara.
"""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import CRUDService
from app.core.exceptions import ConflictoError, ReferenciaInvalidaError
from app.modules.almacenes.models.producto_lote import ProductoLote
from app.modules.almacenes.services.stock_service import (
    sincronizar_precio_de_tienda,
)
from app.modules.movimientos.models.guia_remision_detalle import GuiaRemisionDetalle
from app.modules.productos.services.unidad_de_venta import unidad_venta_de
from app.modules.unidades.services.conversion import a_unidades_minimas


async def lotes_en_unidad_minima(
    db: AsyncSession,
    guia_remision_id: UUID | None,
    producto_id: UUID,
    excluir_lote: UUID | None = None,
) -> int:
    """Lo ya recibido de ese producto en esa guía, en unidad mínima.

    Un solo `SUM` y una sola conversión: todos los lotes de un producto están
    en su unidad de venta, así que no hay nada que agrupar por unidad.
    """
    if guia_remision_id is None:
        return 0

    condiciones = [
        ProductoLote.guia_remision_id == guia_remision_id,
        ProductoLote.producto_id == producto_id,
        ProductoLote.is_active.is_(True),
    ]
    if excluir_lote is not None:
        # El propio lote no cuenta: se está sustituyendo su cantidad.
        condiciones.append(ProductoLote.id != excluir_lote)

    cantidad = await db.scalar(
        select(func.coalesce(func.sum(ProductoLote.cantidad), 0)).where(*condiciones)
    )
    # Sin lotes no hace falta el factor: exigir la equivalencia para dar por
    # buena una suma de cero sería un bloqueo sin sentido.
    if not cantidad:
        return 0
    return await a_unidades_minimas(
        db, cantidad, await unidad_venta_de(db, producto_id)
    )


class ProductoLoteService(CRUDService[ProductoLote]):
    modelo = ProductoLote
    entidad = "Lote"
    campos_unicos: ClassVar[dict[str, str | None]] = {
        "codigo_lote": "producto_id",
    }

    async def crear(
        self, datos: BaseModel, usuario_id: UUID | None = None
    ) -> ProductoLote:
        valores = datos.model_dump()
        await self._validar_contra_guia(
            valores.get("guia_remision_id"),
            valores["producto_id"],
            valores["cantidad"],
        )
        # El lote y su ficha entran en la misma transacción: registrar un lote
        # es decir que ese producto vive en ese almacén, y sin ficha el stock
        # quedaría sin precio con el que venderlo ni mínimo contra el cual
        # medirlo.
        lote = await self._crear_sin_guardar(datos, usuario_id)
        await sincronizar_precio_de_tienda(
            self.db, lote.almacen_id, lote.producto_id, usuario_id
        )
        await self._guardar(lote)
        return lote

    async def actualizar(
        self, registro_id: UUID, datos: BaseModel, usuario_id: UUID | None = None
    ) -> ProductoLote:
        lote = await self.obtener(registro_id)
        cambios = datos.model_dump(exclude_unset=True)
        # Se valida el estado resultante, no solo lo que llega: mover el lote a
        # otra guía o a otro producto también cambia contra qué se compara.
        await self._validar_contra_guia(
            cambios.get("guia_remision_id", lote.guia_remision_id),
            cambios.get("producto_id", lote.producto_id),
            cambios.get("cantidad", lote.cantidad),
            excluir_lote=lote.id,
        )
        # El lote de antes también se sincroniza: si la edición lo mueve a otro
        # almacén o a otro producto, la ficha que dejó atrás se quedaría con un
        # precio que ya no sale de ningún lote suyo.
        anterior = (lote.almacen_id, lote.producto_id)
        actualizado = await self._aplicar_cambios(registro_id, datos, usuario_id)
        for almacen_id, producto_id in {
            anterior,
            (actualizado.almacen_id, actualizado.producto_id),
        }:
            await sincronizar_precio_de_tienda(
                self.db, almacen_id, producto_id, usuario_id
            )
        await self._guardar(actualizado)
        return actualizado

    async def desactivar(
        self, registro_id: UUID, usuario_id: UUID | None = None
    ) -> ProductoLote:
        """Dar de baja el lote saca su precio del cálculo de la tienda."""
        lote = await self._desactivar_sin_guardar(registro_id, usuario_id)
        await sincronizar_precio_de_tienda(
            self.db, lote.almacen_id, lote.producto_id, usuario_id
        )
        await self._guardar(lote)
        return lote

    async def _validar_contra_guia(
        self,
        guia_remision_id: UUID | None,
        producto_id: UUID,
        cantidad: int,
        excluir_lote: UUID | None = None,
    ) -> None:
        """Compara lote y guía **en unidad mínima**.

        La guía viene por paquetes y el lote en la unidad de venta del
        producto, así que comparar los números en crudo daría por buena una
        guía de 4 cajas contra 4 unidades sueltas.

        Sin guía no hay nada contra qué cuadrar: es el lote que entró por una
        recepción contra orden de compra directa, y su respaldo documental es
        esa recepción, que ya se validó por su lado.
        """
        if guia_remision_id is None:
            return

        linea = (
            await self.db.execute(
                select(
                    GuiaRemisionDetalle.cantidad,
                    GuiaRemisionDetalle.unidad_medida_id,
                ).where(
                    GuiaRemisionDetalle.guia_remision_id == guia_remision_id,
                    GuiaRemisionDetalle.producto_id == producto_id,
                    GuiaRemisionDetalle.is_active.is_(True),
                )
            )
        ).first()
        if linea is None:
            raise ReferenciaInvalidaError(
                "La guía de remisión no declara ese producto: registre primero "
                "la línea de la guía."
            )
        declarado = await a_unidades_minimas(
            self.db, linea.cantidad, linea.unidad_medida_id
        )

        ya_registrado = await lotes_en_unidad_minima(
            self.db, guia_remision_id, producto_id, excluir_lote
        )
        entrante = await a_unidades_minimas(
            self.db, cantidad, await unidad_venta_de(self.db, producto_id)
        )

        if ya_registrado + entrante > declarado:
            raise ConflictoError(
                f"Los lotes de este producto sumarían "
                f"{ya_registrado + entrante} unidades mínimas y la guía declara "
                f"{declarado}. Corrija la cantidad del lote o la línea de la guía."
            )
