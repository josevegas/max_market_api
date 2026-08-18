"""Lotes recibidos, cuadrados contra lo que declara la guía de remisión.

Un lote es el bulto físico (con su código y su vencimiento); la línea de la
guía es lo que el documento dice que llegó. Una línea puede partirse en varios
lotes —vencimientos distintos, por ejemplo—, pero la suma de esos lotes no
puede superar lo declarado: si lo hiciera, el almacén acabaría con más stock
del que respalda el documento y el descuadre no aparecería hasta un inventario.
"""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.crud import CRUDService
from app.core.exceptions import ConflictoError, ReferenciaInvalidaError
from app.modules.almacenes.models.producto_lote import ProductoLote
from app.modules.movimientos.models.guia_remision_detalle import GuiaRemisionDetalle
from app.modules.unidades.services.conversion import a_unidades_minimas


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
            valores["guia_remision_id"],
            valores["producto_id"],
            valores["cantidad"],
            valores["unidad_medida_id"],
        )
        return await super().crear(datos, usuario_id)

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
            cambios.get("unidad_medida_id", lote.unidad_medida_id),
            excluir_lote=lote.id,
        )
        return await super().actualizar(registro_id, datos, usuario_id)

    async def _validar_contra_guia(
        self,
        guia_remision_id: UUID,
        producto_id: UUID,
        cantidad: int,
        unidad_medida_id: UUID,
        excluir_lote: UUID | None = None,
    ) -> None:
        """Compara lote y guía **en unidad mínima**.

        La guía viene por paquetes y el almacén guarda en unidad mínima, así
        que comparar los números en crudo daría por buena una guía de 4 cajas
        contra 4 unidades sueltas.
        """
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

        condiciones = [
            ProductoLote.guia_remision_id == guia_remision_id,
            ProductoLote.producto_id == producto_id,
            ProductoLote.is_active.is_(True),
        ]
        if excluir_lote is not None:
            # El propio lote no cuenta: se está sustituyendo su cantidad.
            condiciones.append(ProductoLote.id != excluir_lote)

        ya_registrado = await self._suma_en_unidad_minima(condiciones)
        entrante = await a_unidades_minimas(self.db, cantidad, unidad_medida_id)

        if ya_registrado + entrante > declarado:
            raise ConflictoError(
                f"Los lotes de este producto sumarían "
                f"{ya_registrado + entrante} unidades mínimas y la guía declara "
                f"{declarado}. Corrija la cantidad del lote o la línea de la guía."
            )

    async def _suma_en_unidad_minima(self, condiciones: list) -> int:
        """Suma de los lotes que cumplan `condiciones`, en unidad mínima.

        Se agrupa por unidad y se convierte cada grupo: distintos lotes de la
        misma guía pueden haber entrado en unidades distintas.
        """
        filas = await self.db.execute(
            select(
                ProductoLote.unidad_medida_id,
                func.coalesce(func.sum(ProductoLote.cantidad), 0),
            )
            .where(*condiciones)
            .group_by(ProductoLote.unidad_medida_id)
        )
        total = 0
        for unidad_id, cantidad in filas:
            total += await a_unidades_minimas(self.db, cantidad, unidad_id)
        return total
