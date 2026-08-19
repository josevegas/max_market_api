"""Líneas de recepción, cuadradas contra lo que la guía declaró.

La guía dice qué trae el proveedor; la recepción, qué se aceptó de eso. Que lo
ingresado no supere lo declarado es la razón de ser del documento: si se
pudiera recibir más de lo que la guía trae, el stock quedaría sin respaldo
documental y el descuadre no aparecería hasta el inventario.

Se compara **en unidad mínima**, como en `GuiaRemisionDetalleService`: la guía
puede venir en cajas y la recepción en unidades sueltas, y comparar los números
en crudo daría por buenas 12 cajas contra 12 unidades.

Y lo que se recibe **entra al stock**: cada línea alimenta el lote de su almacén
(ver `stock_service`). Antes eran dos actos separados —recibir y cargar el
lote a mano— y nada garantizaba que dijeran lo mismo.
"""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.crud import CRUDService
from app.core.exceptions import ConflictoError, ReferenciaInvalidaError
from app.modules.almacenes.services.stock_service import sincronizar_desde_linea
from app.modules.movimientos.models.guia_remision_detalle import GuiaRemisionDetalle
from app.modules.movimientos.models.recepcion import Recepcion
from app.modules.movimientos.models.recepcion_detalle import RecepcionDetalle
from app.modules.unidades.services.conversion import a_unidades_minimas


class RecepcionDetalleService(CRUDService[RecepcionDetalle]):
    modelo = RecepcionDetalle
    entidad = "Línea de recepción"
    campos_unicos: ClassVar[dict[str, str | None]] = {
        "producto_id": "recepcion_id",
    }

    async def crear(
        self, datos: BaseModel, usuario_id: UUID | None = None
    ) -> RecepcionDetalle:
        valores = datos.model_dump()
        await self._validar_contra_guia(
            valores["recepcion_id"],
            valores["producto_id"],
            valores.get("cantidad_ingresada", 0),
            valores["unidad_medida_id"],
        )
        # El stock entra en la misma transacción que la línea: si el lote
        # fallara, la recepción no puede quedar registrada como hecha.
        linea = await self._crear_sin_guardar(datos, usuario_id)
        await self._sincronizar_stock(linea, usuario_id)
        await self._guardar(linea)
        return linea

    async def actualizar(
        self, registro_id: UUID, datos: BaseModel, usuario_id: UUID | None = None
    ) -> RecepcionDetalle:
        linea = await self.obtener(registro_id)
        cambios = datos.model_dump(exclude_unset=True)
        await self._validar_contra_guia(
            cambios.get("recepcion_id", linea.recepcion_id),
            cambios.get("producto_id", linea.producto_id),
            cambios.get("cantidad_ingresada", linea.cantidad_ingresada),
            cambios.get("unidad_medida_id", linea.unidad_medida_id),
            excluir_id=linea.id,
        )
        # El lote de antes también se recalcula: si la edición mueve la línea a
        # otro código de lote o a otro producto, el stock que dejó atrás tiene
        # que bajar. Sin esto la mercadería quedaría contada dos veces.
        anterior = (linea.recepcion_id, linea.producto_id, linea.codigo_lote)
        actualizada = await self._aplicar_cambios(registro_id, datos, usuario_id)
        await self._sincronizar_stock(actualizada, usuario_id, ademas=anterior)
        await self._guardar(actualizada)
        return actualizada

    async def desactivar(
        self, registro_id: UUID, usuario_id: UUID | None = None
    ) -> RecepcionDetalle:
        """Dar de baja la línea saca del stock lo que había ingresado."""
        linea = await self._desactivar_sin_guardar(registro_id, usuario_id)
        await self._sincronizar_stock(linea, usuario_id)
        await self._guardar(linea)
        return linea

    async def _sincronizar_stock(
        self,
        linea: RecepcionDetalle,
        usuario_id: UUID | None,
        ademas: tuple[UUID, UUID, str | None] | None = None,
    ) -> None:
        """Recalcula el lote de la línea, y el que haya dejado atrás."""
        objetivos = {(linea.recepcion_id, linea.producto_id, linea.codigo_lote)}
        if ademas is not None:
            objetivos.add(ademas)
        for recepcion_id, producto_id, codigo in objetivos:
            await sincronizar_desde_linea(
                self.db, recepcion_id, producto_id, codigo, usuario_id
            )

    async def _validar_contra_guia(
        self,
        recepcion_id: UUID,
        producto_id: UUID,
        cantidad_ingresada: int,
        unidad_medida_id: UUID,
        excluir_id: UUID | None = None,
    ) -> None:
        recepcion = await self.db.get(Recepcion, recepcion_id)
        if recepcion is None:
            raise ReferenciaInvalidaError(f"La recepción {recepcion_id} no existe.")

        # Una recepción contra orden de compra directa no tiene guía contra la
        # que cuadrar. No es un error: es el caso en que el proveedor entrega
        # sin guía previa y la recepción es el primer papel que lo registra.
        if recepcion.guia_remision_id is None:
            return

        declarado = await self._declarado_en_la_guia(
            recepcion.guia_remision_id, producto_id
        )
        if declarado is None:
            raise ReferenciaInvalidaError(
                f"La guía de remisión {recepcion.guia_remision_id} no declara "
                "este producto, así que no se puede recibir contra ella."
            )

        ingresado = await self._ya_ingresado(recepcion_id, producto_id, excluir_id)
        ingresado += (
            await a_unidades_minimas(self.db, cantidad_ingresada, unidad_medida_id)
            if cantidad_ingresada
            else 0
        )

        if ingresado > declarado:
            raise ConflictoError(
                f"La recepción quedaría en {ingresado} unidades mínimas de este "
                f"producto y la guía solo declara {declarado}."
            )

    async def _declarado_en_la_guia(
        self, guia_remision_id: UUID, producto_id: UUID
    ) -> int | None:
        """Lo que la guía trae de ese producto, en unidad mínima.

        `None` si la guía no lo declara, que es distinto de declarar cero.
        """
        filas = (
            await self.db.execute(
                select(
                    GuiaRemisionDetalle.unidad_medida_id,
                    GuiaRemisionDetalle.cantidad,
                ).where(
                    GuiaRemisionDetalle.guia_remision_id == guia_remision_id,
                    GuiaRemisionDetalle.producto_id == producto_id,
                    GuiaRemisionDetalle.is_active.is_(True),
                )
            )
        ).all()
        if not filas:
            return None

        total = 0
        for unidad_id, cantidad in filas:
            total += (
                await a_unidades_minimas(self.db, cantidad, unidad_id)
                if cantidad
                else 0
            )
        return total

    async def _ya_ingresado(
        self, recepcion_id: UUID, producto_id: UUID, excluir_id: UUID | None
    ) -> int:
        """Lo que otras líneas de la misma recepción ya cargaron del producto.

        La línea que se está tocando se excluye: si no, se contaría con su
        valor anterior y encima del nuevo.
        """
        condiciones = [
            RecepcionDetalle.recepcion_id == recepcion_id,
            RecepcionDetalle.producto_id == producto_id,
            RecepcionDetalle.is_active.is_(True),
        ]
        if excluir_id is not None:
            condiciones.append(RecepcionDetalle.id != excluir_id)

        filas = (
            await self.db.execute(
                select(
                    RecepcionDetalle.unidad_medida_id,
                    func.coalesce(func.sum(RecepcionDetalle.cantidad_ingresada), 0),
                )
                .where(*condiciones)
                .group_by(RecepcionDetalle.unidad_medida_id)
            )
        ).all()

        total = 0
        for unidad_id, cantidad in filas:
            total += (
                await a_unidades_minimas(self.db, cantidad, unidad_id)
                if cantidad
                else 0
            )
        return total
