"""La factura del proveedor contra una orden de compra.

Es el documento del proveedor y no uno nuestro, así que las reglas son
distintas de las de la cadena: no genera sucesor ni exige un padre aprobado en
el sentido estricto. Lo que sí se comprueba es que cobre algo que se pidió:

* la orden existe y alguien la visó —`APROBADO` o `ATENDIDO`—. La factura
  llega antes de recibir la mercadería o después, y las dos son normales; por
  eso no vale `DocumentoEncadenadoService`, que exige `APROBADO` a secas y
  dejaría fuera el caso más común, el de facturar lo ya recepcionado;
* si viene con guía, esa guía pertenece a esa orden;
* quien factura es el proveedor de la orden, que se resuelve por
  `orden.cotizacion_id → cotizacion.proveedor_id`: la orden no lo lleva
  (ver `OrdenCompra`).

El `monto_total` **no** se compara para bloquear. Entregas parciales, fletes y
notas de ajuste hacen que casi nunca coincida con la orden, y exigir igualdad
frenaría operación legítima. Se informa la diferencia al leer la factura, que
es lo que necesita quien la revisa.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select

from app.core.crud import CRUDService
from app.core.exceptions import ConflictoError, ReferenciaInvalidaError
from app.modules.facturas.models.factura import Factura
from app.modules.movimientos.constantes import CODIGO_APROBADO, CODIGO_ATENDIDO
from app.modules.movimientos.models.cotizacion import Cotizacion
from app.modules.movimientos.models.guia_remision import GuiaRemision
from app.modules.movimientos.models.orden_compra import OrdenCompra
from app.modules.movimientos.services.cadena import NaceEnPendiente, codigo_de_estado

#: Estados de la orden desde los que se puede facturar.
FACTURABLES = (CODIGO_APROBADO, CODIGO_ATENDIDO)


class FacturaService(NaceEnPendiente[Factura], CRUDService[Factura]):
    modelo = Factura
    entidad = "Factura"
    campos_unicos: ClassVar[dict[str, str | None]] = {}

    # ── Lectura ─────────────────────────────────────────────────────────────

    async def obtener(self, registro_id: UUID) -> Factura:
        return (await self._anotar([await super().obtener(registro_id)]))[0]

    async def listar(self, **kwargs: Any) -> list[Factura]:
        return await self._anotar(await super().listar(**kwargs))

    async def _anotar(self, facturas: list[Factura]) -> list[Factura]:
        """Le cuelga a cada factura el monto de su orden y si difiere.

        Son atributos de la instancia y no columnas: guardar el monto de la
        orden sería duplicarlo, y quedaría desactualizado en cuanto la orden
        cambie. Se resuelve al leer.
        """
        montos = await self._montos_de_ordenes({f.orden_compra_id for f in facturas})
        for factura in facturas:
            monto = montos.get(factura.orden_compra_id)
            factura.monto_orden = monto
            factura.difiere_de_la_orden = (
                monto is not None and monto != factura.monto_total
            )
        return facturas

    async def _montos_de_ordenes(self, ordenes: Iterable[UUID]) -> dict[UUID, Decimal]:
        """Una sola consulta para todo el listado, no una por fila."""
        ids = [o for o in ordenes if o is not None]
        if not ids:
            return {}
        filas = await self.db.execute(
            select(OrdenCompra.id, OrdenCompra.monto_total).where(
                OrdenCompra.id.in_(ids)
            )
        )
        return dict(filas.all())

    # ── Escritura ───────────────────────────────────────────────────────────

    async def crear(self, datos: BaseModel, usuario_id: UUID | None = None) -> Factura:
        valores = datos.model_dump()
        await self._validar(
            valores["orden_compra_id"],
            valores.get("guia_remision_id"),
            valores["proveedor_id"],
        )
        return (await self._anotar([await super().crear(datos, usuario_id)]))[0]

    async def actualizar(
        self, registro_id: UUID, datos: BaseModel, usuario_id: UUID | None = None
    ) -> Factura:
        """Reapuntar la factura revalida.

        Se mira el estado resultante y no solo lo que llega: mover la factura a
        otra orden, a otra guía o a otro proveedor cambia contra qué se
        compara, y sin esto quedaba el hueco de crear bien y corregir después.
        """
        factura = await super().obtener(registro_id)
        cambios = datos.model_dump(exclude_unset=True)
        await self._validar(
            cambios.get("orden_compra_id", factura.orden_compra_id),
            cambios.get("guia_remision_id", factura.guia_remision_id),
            cambios.get("proveedor_id", factura.proveedor_id),
        )
        actualizada = await super().actualizar(registro_id, datos, usuario_id)
        return (await self._anotar([actualizada]))[0]

    # ── Reglas ──────────────────────────────────────────────────────────────

    async def _validar(
        self, orden_id: UUID, guia_id: UUID | None, proveedor_id: UUID
    ) -> None:
        orden = await self.db.get(OrdenCompra, orden_id)
        if orden is None:
            raise ReferenciaInvalidaError(
                f"La orden de compra {orden_id} no existe: sin ella no se sabe "
                "qué se está facturando."
            )

        codigo = await codigo_de_estado(self.db, orden.estado_id)
        if codigo not in FACTURABLES:
            raise ConflictoError(
                f"La orden de compra {orden_id} está en estado "
                f"'{codigo or 'sin estado'}' y solo se puede facturar una "
                "aprobada o ya atendida."
            )

        if guia_id is not None:
            guia = await self.db.get(GuiaRemision, guia_id)
            if guia is None:
                raise ReferenciaInvalidaError(
                    f"La guía de remisión {guia_id} no existe."
                )
            if guia.orden_compra_id != orden_id:
                raise ConflictoError(
                    f"La guía {guia_id} pertenece a la orden de compra "
                    f"{guia.orden_compra_id}, no a la {orden_id}."
                )

        de_la_orden = await self._proveedor_de(orden)
        if de_la_orden is not None and de_la_orden != proveedor_id:
            raise ConflictoError(
                f"La orden de compra {orden_id} es del proveedor "
                f"{de_la_orden} y la factura la emite {proveedor_id}. Solo "
                "factura quien recibió la orden."
            )

    async def _proveedor_de(self, orden: OrdenCompra) -> UUID | None:
        """El proveedor de la orden, que vive en su cotización.

        `None` si la cotización no está: no es asunto de esta validación
        inventar el eslabón que falte.
        """
        cotizacion = await self.db.get(Cotizacion, orden.cotizacion_id)
        return cotizacion.proveedor_id if cotizacion is not None else None
