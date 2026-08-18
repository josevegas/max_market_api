"""Detalle cuyas líneas alimentan el total de su cabecera.

Cotización y orden de compra necesitan exactamente lo mismo: al tocar una
línea, recalcular el importe de esa línea y el total del documento. Vive acá
una sola vez para que las dos no se puedan desincronizar.

El importe siempre se deriva de `cantidad * precio_unitario`. El cliente no lo
envía: si pudiera, nada garantizaría que cuadrase con los factores que lo
acompañan, y el descuadre no se vería hasta que alguien sumase a mano.
"""

from __future__ import annotations

from decimal import Decimal
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.crud import CRUDService, ModeloT


class DetalleConTotalService(CRUDService[ModeloT]):
    """CRUD de un detalle que mantiene al día el total de su cabecera."""

    #: Modelo de la cabecera (Cotizacion, OrdenCompra...).
    cabecera: ClassVar[type]
    #: Columna del detalle que apunta a la cabecera.
    campo_cabecera: ClassVar[str]
    #: Columna del total en la cabecera.
    campo_total: ClassVar[str] = "monto_total"
    #: Columna donde el detalle guarda su importe. `None` si no lo almacena y
    #: el total se suma al vuelo desde cantidad y precio.
    campo_monto: ClassVar[str | None] = None

    async def crear(self, datos: BaseModel, usuario_id: UUID | None = None) -> ModeloT:
        linea = await super().crear(datos, usuario_id)
        await self._recalcular(linea)
        return linea

    async def actualizar(
        self, registro_id: UUID, datos: BaseModel, usuario_id: UUID | None = None
    ) -> ModeloT:
        linea = await super().actualizar(registro_id, datos, usuario_id)
        await self._recalcular(linea)
        return linea

    async def desactivar(
        self, registro_id: UUID, usuario_id: UUID | None = None
    ) -> ModeloT:
        """Al dar de baja una línea, el total de la cabecera también baja."""
        linea = await super().desactivar(registro_id, usuario_id)
        await self._recalcular(linea)
        return linea

    async def _recalcular(self, linea: ModeloT) -> None:
        importe = Decimal(linea.cantidad) * linea.precio_unitario
        if self.campo_monto:
            setattr(linea, self.campo_monto, importe)

        columna_monto = (
            getattr(self.modelo, self.campo_monto)
            if self.campo_monto
            else self.modelo.cantidad * self.modelo.precio_unitario
        )
        cabecera_id = getattr(linea, self.campo_cabecera)
        total = await self.db.scalar(
            select(func.coalesce(func.sum(columna_monto), 0)).where(
                getattr(self.modelo, self.campo_cabecera) == cabecera_id,
                self.modelo.is_active.is_(True),
                # La línea recién tocada aún no está confirmada en la BD: se
                # suma aparte para no contarla con su valor anterior.
                self.modelo.id != linea.id,
            )
        )
        if linea.is_active:
            total = total + importe

        documento = await self.db.get(self.cabecera, cabecera_id)
        if documento is not None:
            setattr(documento, self.campo_total, total)
        await self._guardar(linea)
