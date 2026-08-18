"""El pedido y las cotizaciones que salen de aprobarlo.

Es el único eslabón que no genera un sucesor sino varios. Cotizar es pedirle
precio a quien pueda venderlo, y comparar: una sola cotización automática
elegiría proveedor por el operador, que es justo la decisión que la cotización
existe para tomar con datos.
"""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from sqlalchemy import select

from app.core.exceptions import ConflictoError
from app.modules.movimientos.constantes import CODIGO_PENDIENTE
from app.modules.movimientos.models.cotizacion import Cotizacion
from app.modules.movimientos.models.cotizacion_detalle import CotizacionDetalle
from app.modules.movimientos.models.pedido import Pedido
from app.modules.movimientos.models.pedido_detalle import PedidoDetalle
from app.modules.movimientos.models.requerimiento import Requerimiento
from app.modules.movimientos.services.cadena import (
    DocumentoEncadenadoService,
    id_de_codigo,
)
from app.modules.movimientos.services.generacion import GeneraSucesorAlAprobar
from app.modules.proveedores.models.empresa import Empresa
from app.modules.proveedores.models.proveedor_producto import ProveedorProducto


class PedidoService(
    GeneraSucesorAlAprobar[Pedido], DocumentoEncadenadoService[Pedido]
):
    """Un pedido solo nace de un requerimiento aprobado.

    Aprobarlo abre una cotización por cada proveedor que distribuya algo de lo
    pedido, cada una con las líneas que ese proveedor puede atender.
    """

    modelo = Pedido
    entidad = "Pedido"
    campos_unicos: ClassVar[dict[str, str | None]] = {}

    padre: ClassVar[type] = Requerimiento
    campo_padre: ClassVar[str] = "requerimiento_id"
    entidad_padre: ClassVar[str] = "El requerimiento"

    sucesor: ClassVar[type] = Cotizacion
    campo_en_sucesor: ClassVar[str] = "pedido_id"
    detalle: ClassVar[type] = PedidoDetalle
    campo_detalle: ClassVar[str] = "pedido_id"
    detalle_sucesor: ClassVar[type] = CotizacionDetalle
    campo_detalle_sucesor: ClassVar[str] = "cotizacion_id"
    # Las líneas de la cotización llevan precio, pero el pedido no lo tiene:
    # arrancan en cero y las completa el proveedor.
    campo_monto_linea: ClassVar[str] = "monto_producto"

    async def _generar_sucesor(self, documento: Pedido, usuario_id: UUID | None) -> None:
        """Una cotización por proveedor, con lo que cada uno puede atender."""
        if await self._ya_tiene_sucesor(documento.id):
            return

        lineas = await self._lineas_de(documento.id)
        if not lineas:
            # Un pedido sin líneas no tiene productos, y sin productos no hay a
            # quién pedirle precio. No es un error: aprobar la cabecera y
            # cargar el detalle después es una secuencia legítima, y cortarla
            # convertiría la generación en un requisito para aprobar.
            return

        por_proveedor = await self._proveedores_de(
            [linea.producto_id for linea in lineas]
        )
        if not por_proveedor:
            # Acá sí se corta: el pedido pide productos concretos y ninguno
            # tiene proveedor asignado, así que aprobarlo lo dejaría en un
            # callejón sin salida y sin decir por qué. El mensaje nombra dónde
            # se arregla.
            raise ConflictoError(
                "Ningún proveedor distribuye los productos de este pedido, así que "
                "no hay a quién pedirle precio. Asigne proveedores desde la ficha "
                "de la empresa antes de aprobarlo."
            )

        pendiente_id = await id_de_codigo(self.db, CODIGO_PENDIENTE)
        for proveedor_id, plazos in por_proveedor.items():
            suyas = [linea for linea in lineas if linea.producto_id in plazos]
            cotizacion = Cotizacion(
                pedido_id=documento.id,
                proveedor_id=proveedor_id,
                estado_id=pendiente_id,
                fecha=documento.fecha,
                # El plazo de la cotización es el del producto más lento: el
                # pedido no está atendido hasta que llega la última línea.
                tiempo_atencion=max(plazos.values()),
                monto_total=0,
                created_by=usuario_id,
            )
            self.db.add(cotizacion)
            await self.db.flush()
            await self._copiar_lineas(cotizacion, suyas, usuario_id)

    async def _proveedores_de(
        self, producto_ids: list[UUID]
    ) -> dict[UUID, dict[UUID, int]]:
        """Qué proveedor atiende qué producto y en cuántos días.

        Devuelve `{empresa_id: {producto_id: tiempo_atencion}}`. Solo entran
        empresas activas y marcadas como proveedoras: una empresa que dejó de
        serlo no debería recibir un pedido de precio.
        """
        filas = (
            await self.db.execute(
                select(
                    ProveedorProducto.empresa_id,
                    ProveedorProducto.producto_id,
                    ProveedorProducto.tiempo_atencion,
                )
                .join(Empresa, Empresa.id == ProveedorProducto.empresa_id)
                .where(
                    ProveedorProducto.producto_id.in_(producto_ids),
                    ProveedorProducto.is_active.is_(True),
                    Empresa.is_active.is_(True),
                    Empresa.es_proveedor.is_(True),
                )
            )
        ).all()

        por_proveedor: dict[UUID, dict[UUID, int]] = {}
        for empresa_id, producto_id, plazo in filas:
            por_proveedor.setdefault(empresa_id, {})[producto_id] = plazo
        return por_proveedor
