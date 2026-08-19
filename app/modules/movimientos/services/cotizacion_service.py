from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from sqlalchemy import select, update

from app.modules.movimientos.constantes import (
    CODIGO_OBSERVADO,
    CODIGO_PENDIENTE,
    CODIGO_RECHAZADO,
)
from app.modules.movimientos.models.cotizacion import Cotizacion
from app.modules.movimientos.models.cotizacion_detalle import CotizacionDetalle
from app.modules.movimientos.models.estado import Estado
from app.modules.movimientos.models.orden_compra import OrdenCompra
from app.modules.movimientos.models.orden_compra_detalle import OrdenCompraDetalle
from app.modules.movimientos.models.pedido import Pedido
from app.modules.movimientos.services.cadena import (
    DocumentoEncadenadoService,
    NaceEnPendiente,
    id_de_codigo,
)
from app.modules.movimientos.services.generacion import GeneraSucesorAlAprobar


class CotizacionService(
    NaceEnPendiente[Cotizacion],
    GeneraSucesorAlAprobar[Cotizacion],
    DocumentoEncadenadoService[Cotizacion],
):
    """Solo se cotiza contra un pedido aprobado, y aprobarla emite la orden.

    Varios proveedores pueden cotizar el mismo pedido: no hay unicidad por
    `pedido_id`, que es justo lo que permite compararlas antes de ordenar.
    Aprobar una es elegir a ese proveedor, y de ahí que genere la orden de
    compra con sus precios ya puestos.

    Y elegir a uno es no elegir a los otros: aprobar una cotización rechaza las
    hermanas que seguían en carrera. Sin eso quedaban varias aprobadas para el
    mismo pedido, cada una con su orden de compra, y el market terminaba
    comprometido a comprar lo mismo dos veces.
    """

    modelo = Cotizacion
    entidad = "Cotización"
    campos_unicos: ClassVar[dict[str, str | None]] = {}

    padre: ClassVar[type] = Pedido
    campo_padre: ClassVar[str] = "pedido_id"
    entidad_padre: ClassVar[str] = "El pedido"

    sucesor: ClassVar[type] = OrdenCompra
    campo_en_sucesor: ClassVar[str] = "cotizacion_id"
    detalle: ClassVar[type] = CotizacionDetalle
    campo_detalle: ClassVar[str] = "cotizacion_id"
    detalle_sucesor: ClassVar[type] = OrdenCompraDetalle
    campo_detalle_sucesor: ClassVar[str] = "orden_compra_id"
    # La orden compra lo cotizado al precio cotizado: es el compromiso con el
    # proveedor, así que arrastra precios y total.
    sucesor_con_precio: ClassVar[bool] = True
    sucesor_con_total: ClassVar[bool] = True

    async def _al_aprobar(
        self, registro: Cotizacion, usuario_id: UUID | None
    ) -> None:
        """Rechaza las demás cotizaciones del pedido: el proveedor ya se eligió.

        Solo se tocan las que seguían **en carrera** (`PEN` y `OBS`). Una hermana
        que ya estaba aprobada o más adelante en la cadena no se rechaza: tiene
        una orden de compra viva colgando, y darla por rechazada dejaría el
        documento diciendo una cosa y su orden otra. Ese caso solo aparece en
        datos anteriores a esta regla, y se arregla mirándolo, no en silencio.

        Es un `UPDATE` masivo y no un recorrido de objetos: son documentos que
        nadie está leyendo en esta transacción, y traerlos uno por uno para
        cambiarles un campo agregaría tantas consultas como proveedores.
        """
        en_carrera = await self.db.scalars(
            select(Estado.id).where(
                Estado.codigo.in_((CODIGO_PENDIENTE, CODIGO_OBSERVADO)),
                Estado.is_active.is_(True),
            )
        )
        ids_en_carrera = list(en_carrera)
        # Sin `PEN` ni `OBS` en el catálogo no hay a quién rechazar. No es un
        # error: es una base sin sembrar, y ahí no hay hermanas que descartar.
        if not ids_en_carrera:
            return

        await self.db.execute(
            update(Cotizacion)
            .where(
                Cotizacion.pedido_id == registro.pedido_id,
                Cotizacion.id != registro.id,
                Cotizacion.is_active.is_(True),
                Cotizacion.estado_id.in_(ids_en_carrera),
            )
            .values(
                estado_id=await id_de_codigo(self.db, CODIGO_RECHAZADO),
                updated_by=usuario_id,
            )
        )
