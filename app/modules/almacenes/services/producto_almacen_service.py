"""Ficha de un producto en un almacén: mínimos, máximos y precio de tienda.

El `precio_venta_tienda` lo calcula el stock: sale del lote más caro que quede
con existencias (ver `stock_service.precio_de_tienda`). Se cargaba a mano y
nada lo ataba a lo que la mercadería costó, así que podía quedar por debajo del
costo de la partida que todavía estaba en el almacén.

La tienda puede fijarlo igual, marcando `precio_manual`: una promoción es una
decisión comercial, no un error. Con esa marca la sincronización deja de
pisarlo, y quitarla lo devuelve al cálculo.
"""

from __future__ import annotations

from decimal import Decimal
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel

from app.core.crud import CRUDService
from app.modules.almacenes.models.producto_almacen import ProductoAlmacen
from app.modules.almacenes.services.stock_service import precio_de_tienda


class ProductoAlmacenService(CRUDService[ProductoAlmacen]):
    modelo = ProductoAlmacen
    entidad = "Producto en almacén"
    campos_unicos: ClassVar[dict[str, str | None]] = {
        "producto_id": "almacen_id",
    }

    async def crear(
        self, datos: BaseModel, usuario_id: UUID | None = None
    ) -> ProductoAlmacen:
        valores = datos.model_dump()
        if not valores.get("precio_manual"):
            # La ficha suele crearse antes de que entre mercadería. Sin lotes
            # no hay máximo del que sacarlo, y la columna es NOT NULL: arranca
            # en cero y la primera recepción lo deja en su valor.
            valores["precio_venta_tienda"] = await self._calculado(
                valores["almacen_id"], valores["producto_id"]
            )
        await self._validar_unicidad(valores)
        registro = self.modelo(**valores, created_by=usuario_id)
        self.db.add(registro)
        await self._guardar(registro)
        return registro

    async def actualizar(
        self, registro_id: UUID, datos: BaseModel, usuario_id: UUID | None = None
    ) -> ProductoAlmacen:
        """Quitar la marca manual devuelve la ficha al precio calculado.

        Si solo se guardase el `False`, el precio se quedaría en el que fijó la
        tienda hasta la próxima recepción, y quien lo desmarcó vería el valor
        viejo sin entender por qué.
        """
        registro = await self._aplicar_cambios(registro_id, datos, usuario_id)
        cambios = datos.model_dump(exclude_unset=True)
        if cambios.get("precio_manual") is False:
            registro.precio_venta_tienda = await self._calculado(
                registro.almacen_id, registro.producto_id
            )
        await self._guardar(registro)
        return registro

    async def _calculado(self, almacen_id: UUID, producto_id: UUID) -> Decimal:
        precio = await precio_de_tienda(self.db, almacen_id, producto_id)
        return precio if precio is not None else Decimal("0")
