"""Líneas de guía de remisión, cuadradas con los lotes ya registrados.

La regla es la misma que aplica `ProductoLoteService`, mirada desde el otro
lado: si ya hay lotes recibidos, la línea no puede rebajarse por debajo de lo
que suman. Sin esto bastaría con editar la guía para dejar el stock sin
respaldo, esquivando la validación del lote.
"""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.crud import CRUDService
from app.core.exceptions import ConflictoError
from app.modules.almacenes.models.producto_lote import ProductoLote
from app.modules.movimientos.models.guia_remision_detalle import GuiaRemisionDetalle
from app.modules.unidades.services.conversion import a_unidades_minimas


class GuiaRemisionDetalleService(CRUDService[GuiaRemisionDetalle]):
    modelo = GuiaRemisionDetalle
    entidad = "Línea de guía de remisión"
    campos_unicos: ClassVar[dict[str, str | None]] = {
        "producto_id": "guia_remision_id",
    }

    async def actualizar(
        self, registro_id: UUID, datos: BaseModel, usuario_id: UUID | None = None
    ) -> GuiaRemisionDetalle:
        linea = await self.obtener(registro_id)
        cambios = datos.model_dump(exclude_unset=True)
        await self._validar_contra_lotes(
            cambios.get("guia_remision_id", linea.guia_remision_id),
            cambios.get("producto_id", linea.producto_id),
            cambios.get("cantidad", linea.cantidad),
            cambios.get("unidad_medida_id", linea.unidad_medida_id),
        )
        return await super().actualizar(registro_id, datos, usuario_id)

    async def desactivar(
        self, registro_id: UUID, usuario_id: UUID | None = None
    ) -> GuiaRemisionDetalle:
        """Dar de baja la línea equivale a dejarla en cero."""
        linea = await self.obtener(registro_id)
        await self._validar_contra_lotes(
            linea.guia_remision_id, linea.producto_id, 0, linea.unidad_medida_id
        )
        return await super().desactivar(registro_id, usuario_id)

    async def _validar_contra_lotes(
        self,
        guia_remision_id: UUID,
        producto_id: UUID,
        cantidad: int,
        unidad_medida_id: UUID,
    ) -> None:
        """Compara **en unidad mínima**: la línea viene por paquetes."""
        filas = await self.db.execute(
            select(
                ProductoLote.unidad_medida_id,
                func.coalesce(func.sum(ProductoLote.cantidad), 0),
            )
            .where(
                ProductoLote.guia_remision_id == guia_remision_id,
                ProductoLote.producto_id == producto_id,
                ProductoLote.is_active.is_(True),
            )
            .group_by(ProductoLote.unidad_medida_id)
        )
        recibido = 0
        for unidad_id, cant in filas:
            recibido += await a_unidades_minimas(self.db, cant, unidad_id)

        # La línea en cero no necesita factor: es la baja, y exigir una
        # equivalencia para poder anular sería un bloqueo sin sentido.
        declarado = (
            await a_unidades_minimas(self.db, cantidad, unidad_medida_id)
            if cantidad
            else 0
        )

        if recibido > declarado:
            raise ConflictoError(
                f"Ya hay lotes por {recibido} unidades mínimas de este producto "
                f"y la línea quedaría en {declarado}. Ajuste primero los lotes."
            )
