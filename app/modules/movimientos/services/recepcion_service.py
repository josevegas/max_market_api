"""La recepción: el documento que cierra la cadena de compras.

Registrar una recepción no es solo insertar una fila. Es el hecho de negocio
que dice "la mercadería entró", y de ahí se sigue que la guía queda
`RECEPCIONADO` y que todo lo que venía antes —orden, cotización, pedido,
requerimiento— queda `ATENDIDO`: lo que cada uno pedía ya llegó.

Ese arrastre se hace acá, en la misma transacción que el alta. Si se dejara al
cliente (cinco PATCH encadenados), bastaría con que uno fallara para que la
cadena quedase a medias: la guía recepcionada y el requerimiento diciendo que
todavía espera.
"""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel

from app.core.crud import CRUDService
from app.core.exceptions import ConflictoError, ReferenciaInvalidaError
from app.modules.movimientos.constantes import (
    CODIGO_ATENDIDO,
    CODIGO_RECEPCIONADO,
)
from app.modules.movimientos.models.cotizacion import Cotizacion
from app.modules.movimientos.models.guia_remision import GuiaRemision
from app.modules.movimientos.models.orden_compra import OrdenCompra
from app.modules.movimientos.models.pedido import Pedido
from app.modules.movimientos.models.recepcion import Recepcion
from app.modules.movimientos.models.requerimiento import Requerimiento
from app.modules.movimientos.services.cadena import codigo_de_estado, id_de_codigo


class RecepcionService(CRUDService[Recepcion]):
    modelo = Recepcion
    entidad = "Recepción"
    campos_unicos: ClassVar[dict[str, str | None]] = {}

    async def crear(
        self, datos: BaseModel, usuario_id: UUID | None = None
    ) -> Recepcion:
        valores = datos.model_dump()
        guia_id = valores.get("guia_remision_id")
        orden_id = valores.get("orden_compra_id")

        if guia_id is None and orden_id is None:
            raise ReferenciaInvalidaError(
                "La recepción necesita una guía de remisión o una orden de "
                "compra: sin una de las dos no se sabe qué se está recibiendo."
            )

        guia = await self._guia_recepcionable(guia_id)
        if guia is not None:
            # Si llegan los dos, tienen que decir lo mismo. Sin esta
            # comprobación se podría cerrar la cadena de una orden ajena a la
            # guía que de verdad se recibió.
            if orden_id is not None and orden_id != guia.orden_compra_id:
                raise ConflictoError(
                    f"La guía {guia.id} pertenece a la orden de compra "
                    f"{guia.orden_compra_id}, no a la {orden_id}."
                )
            valores["orden_compra_id"] = guia.orden_compra_id

        if valores.get("estado_id") is None:
            valores["estado_id"] = await id_de_codigo(self.db, CODIGO_RECEPCIONADO)

        registro = self.modelo(**valores, created_by=usuario_id)
        self.db.add(registro)
        # El arrastre va antes del commit: las dos cosas entran juntas o no
        # entra ninguna.
        await self._cerrar_cadena(guia, valores.get("orden_compra_id"), usuario_id)
        await self._guardar(registro)
        return registro

    # ── Reglas ──────────────────────────────────────────────────────────────

    async def _guia_recepcionable(self, guia_id: UUID | None) -> GuiaRemision | None:
        """La guía existe y todavía no se recibió."""
        if guia_id is None:
            return None
        guia = await self.db.get(GuiaRemision, guia_id)
        if guia is None:
            raise ReferenciaInvalidaError(f"La guía de remisión {guia_id} no existe.")

        codigo = await codigo_de_estado(self.db, guia.estado_id)
        if codigo == CODIGO_RECEPCIONADO:
            raise ConflictoError(f"La guía de remisión {guia_id} ya está recepcionada.")
        return guia

    async def _cerrar_cadena(
        self,
        guia: GuiaRemision | None,
        orden_id: UUID | None,
        usuario_id: UUID | None,
    ) -> None:
        """Guía a RECEPCIONADO y todo lo anterior a ATENDIDO.

        Se sube hacia atrás por los ids, no por relaciones ORM: los modelos de
        este módulo no declaran `relationship`, y resolverlo con `db.get` deja
        explícito por dónde sube la cadena.
        """
        recepcionado = await id_de_codigo(self.db, CODIGO_RECEPCIONADO)
        atendido = await id_de_codigo(self.db, CODIGO_ATENDIDO)

        if guia is not None:
            guia.estado_id = recepcionado
            guia.updated_by = usuario_id

        orden = await self.db.get(OrdenCompra, orden_id) if orden_id else None
        if orden is None:
            return
        orden.estado_id = atendido
        orden.updated_by = usuario_id

        cotizacion = await self.db.get(Cotizacion, orden.cotizacion_id)
        if cotizacion is None:
            return
        cotizacion.estado_id = atendido
        cotizacion.updated_by = usuario_id

        pedido = await self.db.get(Pedido, cotizacion.pedido_id)
        if pedido is None:
            return
        pedido.estado_id = atendido
        pedido.updated_by = usuario_id

        requerimiento = await self.db.get(Requerimiento, pedido.requerimiento_id)
        if requerimiento is None:
            return
        requerimiento.estado_id = atendido
        requerimiento.updated_by = usuario_id
