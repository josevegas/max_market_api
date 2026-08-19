"""Historial de precios de un producto.

El `precio_venta` no se recibe: lo calcula el servidor a partir del de compra y
del margen de la categoría (ver `calculo_precio`). Se cargaba a mano y nada
obligaba a que respetara el margen que la categoría declaraba, así que el dato
existía en dos versiones que podían decir cosas distintas.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select

from app.core.crud import CRUDService
from app.core.fechas import hoy_en_peru
from app.modules.productos.models.precio_producto import PrecioProducto
from app.modules.productos.services.calculo_precio import calcular_precio_venta


class PrecioProductoService(CRUDService[PrecioProducto]):
    modelo = PrecioProducto
    entidad = "Precio de producto"

    async def crear(
        self, datos: BaseModel, usuario_id: UUID | None = None
    ) -> PrecioProducto:
        valores = datos.model_dump()
        await self._validar_unicidad(valores)
        valores["precio_venta"] = await self._precio_venta(
            valores["producto_id"], valores["precio_compra"]
        )
        registro = self.modelo(**valores, created_by=usuario_id)
        self.db.add(registro)
        await self._guardar(registro)
        return registro

    async def actualizar(
        self, registro_id: UUID, datos: BaseModel, usuario_id: UUID | None = None
    ) -> PrecioProducto:
        """Cambiar el precio de compra recalcula el de venta.

        Si no, corregir lo que costó dejaría el precio al público colgado del
        valor anterior, que es el descuadre que este cálculo viene a evitar.
        """
        registro = await self._aplicar_cambios(registro_id, datos, usuario_id)
        registro.precio_venta = await self._precio_venta(
            registro.producto_id, registro.precio_compra
        )
        await self._guardar(registro)
        return registro

    async def _precio_venta(self, producto_id: UUID, precio_compra: Decimal) -> Decimal:
        return await calcular_precio_venta(self.db, producto_id, precio_compra)

    async def vigente(
        self, producto_id: UUID, en_fecha: date | None = None
    ) -> PrecioProducto | None:
        """Precio que rige para un producto en una fecha.

        Un precio sin `fecha_fin` sigue vigente; entre varios solapados gana el
        de inicio más reciente, que es el último que se cargó.
        """
        # Contra el huso de Perú y no contra el reloj del servidor: si la app
        # corre en UTC, `date.today()` adelanta el día a partir de las 19:00
        # de Lima y daría por vigente un precio que aún no empieza.
        en_fecha = en_fecha or hoy_en_peru()
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
