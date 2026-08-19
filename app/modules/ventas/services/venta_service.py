"""La venta del market, y el stock que se lleva consigo.

Emitir el comprobante y descontar la mercadería son el mismo hecho. Tenerlos
separados era la desconexión que ya existía entre recepción y lote: dos
registros de lo mismo que nada obligaba a cuadrar.

La salida es **FEFO** —vence primero, sale primero—, y cada línea deja anotado
de qué lotes salió (`VentaLote`). Eso permite dos cosas que sin la anotación no
se pueden: devolver el stock exactamente a donde estaba al anular la venta, y
responder a quién se le vendió un lote cuando hay que retirarlo.

El precio lo pone la ficha del almacén (`producto_almacen.precio_venta_tienda`),
que a su vez sale del lote más caro con existencias. La caja no lo envía: si
pudiera, se podría vender por debajo del costo de la partida que está en el
almacén sin que nada avisara.
"""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select

from app.core.crud import CRUDService
from app.core.exceptions import ConflictoError, ReferenciaInvalidaError
from app.modules.almacenes.models.producto_almacen import ProductoAlmacen
from app.modules.almacenes.services.stock_service import (
    descontar_stock,
    devolver_stock,
)
from app.modules.movimientos.services.cadena import NaceEnPendiente
from app.modules.movimientos.services.detalle_con_total import DetalleConTotalService
from app.modules.ventas.models.tipo_comprobante import TipoComprobante
from app.modules.ventas.models.venta import Venta
from app.modules.ventas.models.venta_detalle import VentaDetalle, VentaLote

#: Códigos de comprobante que identifican al cliente por RUC. La boleta se
#: emite sin identificarlo; la factura, no.
COMPROBANTES_CON_RUC = ("01", "FACTURA", "FAC")


class TipoComprobanteService(CRUDService[TipoComprobante]):
    modelo = TipoComprobante
    entidad = "Tipo de comprobante"
    campos_unicos: ClassVar[dict[str, str | None]] = {"codigo": None}


class VentaService(NaceEnPendiente[Venta], CRUDService[Venta]):
    modelo = Venta
    entidad = "Venta"
    campos_unicos: ClassVar[dict[str, str | None]] = {}

    async def crear(self, datos: BaseModel, usuario_id: UUID | None = None) -> Venta:
        valores = datos.model_dump()
        await self._exigir_ruc_si_es_factura(
            valores["tipo_comprobante_id"], valores.get("ruc_cliente")
        )
        return await super().crear(datos, usuario_id)

    async def actualizar(
        self, registro_id: UUID, datos: BaseModel, usuario_id: UUID | None = None
    ) -> Venta:
        venta = await self.obtener(registro_id)
        cambios = datos.model_dump(exclude_unset=True)
        # Se mira el estado resultante: cambiar el tipo de comprobante de
        # boleta a factura exige el RUC que antes no hacía falta.
        await self._exigir_ruc_si_es_factura(
            cambios.get("tipo_comprobante_id", venta.tipo_comprobante_id),
            cambios.get("ruc_cliente", venta.ruc_cliente),
        )
        return await super().actualizar(registro_id, datos, usuario_id)

    async def _exigir_ruc_si_es_factura(self, tipo_id: UUID, ruc: str | None) -> None:
        tipo = await self.db.get(TipoComprobante, tipo_id)
        if tipo is None:
            raise ReferenciaInvalidaError(
                f"El tipo de comprobante {tipo_id} no existe."
            )
        if tipo.codigo.upper() in COMPROBANTES_CON_RUC and not ruc:
            raise ConflictoError(
                f"El comprobante '{tipo.descripcion}' identifica al cliente: "
                "falta el RUC."
            )


class VentaDetalleService(DetalleConTotalService[VentaDetalle]):
    modelo = VentaDetalle
    entidad = "Línea de venta"
    campos_unicos: ClassVar[dict[str, str | None]] = {
        "producto_id": "venta_id",
    }

    cabecera: ClassVar[type] = Venta
    campo_cabecera: ClassVar[str] = "venta_id"
    campo_monto: ClassVar[str] = "monto"

    async def crear(
        self, datos: BaseModel, usuario_id: UUID | None = None
    ) -> VentaDetalle:
        valores = datos.model_dump()
        venta = await self._venta(valores["venta_id"])
        valores["precio_unitario"] = await self._precio(
            venta.almacen_id, valores["producto_id"]
        )

        # El stock se toca antes de crear la línea: si no alcanza, la venta no
        # llega a tener detalle y el comprobante queda sin nada que respaldar.
        consumido = await descontar_stock(
            self.db,
            venta.almacen_id,
            valores["producto_id"],
            valores["cantidad"],
            usuario_id,
        )

        linea = self.modelo(**valores, created_by=usuario_id)
        self.db.add(linea)
        await self._vaciar()
        self._anotar_lotes(linea, consumido, usuario_id)
        await self._recalcular(linea)
        return linea

    async def actualizar(
        self, registro_id: UUID, datos: BaseModel, usuario_id: UUID | None = None
    ) -> VentaDetalle:
        """Corregir la cantidad devuelve todo y vuelve a sacar.

        Ajustar la diferencia sería más corto y más frágil: bajar de 30 a 10
        tendría que decidir a qué lotes devolver 20, y esa decisión ya la tomó
        el FEFO cuando salieron. Devolver y repetir deja el almacén como si la
        línea se hubiera cargado bien la primera vez.
        """
        linea = await self.obtener(registro_id)
        cambios = datos.model_dump(exclude_unset=True)
        cantidad = cambios.get("cantidad", linea.cantidad)
        venta = await self._venta(linea.venta_id)

        await self._devolver_lotes(linea, usuario_id)
        consumido = await descontar_stock(
            self.db, venta.almacen_id, linea.producto_id, cantidad, usuario_id
        )

        actualizada = await self._aplicar_cambios(registro_id, datos, usuario_id)
        self._anotar_lotes(actualizada, consumido, usuario_id)
        await self._recalcular(actualizada)
        return actualizada

    async def desactivar(
        self, registro_id: UUID, usuario_id: UUID | None = None
    ) -> VentaDetalle:
        """Anular la línea devuelve la mercadería a sus lotes."""
        linea = await self.obtener(registro_id)
        await self._devolver_lotes(linea, usuario_id)
        baja = await self._desactivar_sin_guardar(registro_id, usuario_id)
        await self._recalcular(baja)
        return baja

    # ── Interno ─────────────────────────────────────────────────────────────

    async def _venta(self, venta_id: UUID) -> Venta:
        venta = await self.db.get(Venta, venta_id)
        if venta is None:
            raise ReferenciaInvalidaError(f"La venta {venta_id} no existe.")
        return venta

    async def _precio(self, almacen_id: UUID, producto_id: UUID):
        """El precio de la ficha de ese producto en ese almacén."""
        precio = await self.db.scalar(
            select(ProductoAlmacen.precio_venta_tienda).where(
                ProductoAlmacen.almacen_id == almacen_id,
                ProductoAlmacen.producto_id == producto_id,
                ProductoAlmacen.is_active.is_(True),
            )
        )
        if precio is None:
            raise ReferenciaInvalidaError(
                "El producto no tiene ficha en este almacén: sin ella no hay "
                "precio de venta. Créela antes de vender."
            )
        return precio

    def _anotar_lotes(self, linea, consumido, usuario_id: UUID | None) -> None:
        """Deja escrito de qué lote salió cada unidad."""
        for lote, cantidad in consumido:
            self.db.add(
                VentaLote(
                    venta_detalle_id=linea.id,
                    producto_lote_id=lote.id,
                    cantidad=cantidad,
                    created_by=usuario_id,
                )
            )

    async def _devolver_lotes(self, linea, usuario_id: UUID | None) -> None:
        """Devuelve lo que esta línea sacó y borra el rastro.

        Las anotaciones se eliminan en vez de darse de baja: no describen un
        hecho histórico sino de dónde está saliendo el stock **ahora**, y una
        anotación inactiva que apunta a mercadería ya devuelta solo puede
        confundir a quien rastree un lote.
        """
        anotaciones = (
            (
                await self.db.execute(
                    select(VentaLote).where(VentaLote.venta_detalle_id == linea.id)
                )
            )
            .scalars()
            .all()
        )
        for anotacion in anotaciones:
            await devolver_stock(
                self.db, anotacion.producto_lote_id, anotacion.cantidad, usuario_id
            )
            await self.db.delete(anotacion)
        await self._vaciar()
