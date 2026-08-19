"""Aprobar un documento genera el siguiente de la cadena.

    requerimiento → pedido → cotización → orden de compra → guía de remisión

`cadena.py` pone la mitad de la regla: un documento solo nace si su padre está
aprobado. Acá va la otra mitad: aprobar el padre **crea** al hijo. Sin esto la
aprobación era un cambio de estado que no producía nada, y quien operaba tenía
que acordarse de ir a la pantalla siguiente y volver a teclear las mismas
líneas.

Todo ocurre en la misma transacción que la aprobación, igual que el arrastre de
`RecepcionService`: si el hijo no se puede crear, el padre tampoco queda
aprobado. Repartirlo en dos llamadas dejaría documentos aprobados sin sucesor y
nadie se enteraría hasta que alguien buscara el pedido que nunca se generó.

El hijo nace **pendiente**, no aprobado: generarlo es proponer el siguiente
paso, no darlo por bueno. Aprobarlo es una decisión aparte, que a su vez
generará el suyo.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.crud import CRUDService, ModeloT
from app.core.exceptions import ConflictoError
from app.modules.movimientos.constantes import CODIGO_APROBADO, CODIGO_PENDIENTE
from app.modules.movimientos.services.cadena import id_de_codigo


class GeneraSucesorAlAprobar(CRUDService[ModeloT]):
    """CRUD de un documento que, al pasar a `APR`, crea el siguiente.

    Las subclases declaran de qué está hecho el sucesor con los `ClassVar` de
    abajo. Cuando eso no alcanza —el pedido genera *varias* cotizaciones, una
    por proveedor— se sobreescribe `_generar_sucesor`.
    """

    #: Modelo del documento que se genera.
    sucesor: ClassVar[type]
    #: Columna del sucesor que apunta a este documento.
    campo_en_sucesor: ClassVar[str]
    #: Detalle de este documento y columna con la que apunta a su cabecera.
    detalle: ClassVar[type]
    campo_detalle: ClassVar[str]
    #: Detalle del sucesor y su columna de cabecera.
    detalle_sucesor: ClassVar[type]
    campo_detalle_sucesor: ClassVar[str]
    #: Si las líneas del sucesor llevan precio, se arrastra el de este
    #: documento; si no lo tiene (requerimiento, pedido), arrancan en cero.
    sucesor_con_precio: ClassVar[bool] = False
    #: Columna donde la línea del sucesor guarda su importe, si lo almacena.
    #: `CotizacionDetalle` lo hace en `monto_producto`; la línea de la orden lo
    #: deriva al vuelo y no tiene columna.
    campo_monto_linea: ClassVar[str | None] = None
    #: Si el sucesor lleva `monto_total`, se calcula al copiar. Dejarlo en cero
    #: y esperar a que alguien toque una línea haría que el documento recién
    #: generado mostrara un total que no es el suyo.
    sucesor_con_total: ClassVar[bool] = False

    async def actualizar(
        self, registro_id: UUID, datos: BaseModel, usuario_id: UUID | None = None
    ) -> ModeloT:
        aprobado_id = await id_de_codigo(self.db, CODIGO_APROBADO)
        registro = await self.obtener(registro_id)
        # Se compara contra el estado **previo**: reaprobar algo ya aprobado no
        # es una aprobación, y sin esta guarda cada PATCH de la fecha volvería a
        # disparar la generación.
        venia_aprobado = registro.estado_id == aprobado_id

        registro = await self._aplicar_cambios(registro_id, datos, usuario_id)
        if not venia_aprobado and registro.estado_id == aprobado_id:
            # Antes de generar el sucesor y en su propio bloque: sus errores no
            # son "no se pudo generar el documento siguiente", y traducirlos con
            # ese mensaje mandaría a mirar el lugar equivocado.
            await self._al_aprobar(registro, usuario_id)
            try:
                await self._generar_sucesor(registro, usuario_id)
            except IntegrityError as exc:
                # El `flush` de la generación puede chocar con una restricción.
                # Sin traducirlo sale como 500, y sin el rollback la sesión
                # queda con una transacción abortada: la aprobación seguiría en
                # memoria como hecha cuando en la base no entró nada.
                await self.db.rollback()
                raise ConflictoError(
                    f"No se pudo generar el documento siguiente a {self.entidad.lower()} "
                    f"{registro_id}: choca con una restricción de la base."
                ) from exc
            except Exception:
                await self.db.rollback()
                raise

        await self._guardar(registro)
        return registro

    async def _al_aprobar(self, registro: ModeloT, usuario_id: UUID | None) -> None:
        """Efectos colaterales de la **primera** aprobación, además del sucesor.

        Existe como gancho y no resuelto en cada servicio para no duplicar la
        detección de "recién aprobado": `venia_aprobado` es la única guarda que
        distingue una aprobación de un PATCH cualquiera sobre un documento ya
        aprobado, y una segunda copia de esa lógica acabaría diciendo otra cosa.

        Por defecto no hace nada. Hoy solo la cotización lo usa, para descartar
        a las hermanas cuando se elige un proveedor.
        """

    # ── Generación ──────────────────────────────────────────────────────────

    async def _generar_sucesor(
        self, documento: ModeloT, usuario_id: UUID | None
    ) -> None:
        """Un sucesor con las mismas líneas, en estado pendiente."""
        if await self._ya_tiene_sucesor(documento.id):
            return

        pendiente_id = await id_de_codigo(self.db, CODIGO_PENDIENTE)
        hijo = self.sucesor(
            **{self.campo_en_sucesor: documento.id},
            **self._campos_extra(documento),
            estado_id=pendiente_id,
            fecha=documento.fecha,
            created_by=usuario_id,
        )
        self.db.add(hijo)
        # `flush` y no `commit`: hace falta el id del hijo para colgarle las
        # líneas, pero la transacción tiene que seguir abierta hasta que la
        # aprobación se guarde con ellas.
        await self.db.flush()
        await self._copiar_lineas(hijo, await self._lineas_de(documento.id), usuario_id)

    def _campos_extra(self, documento: ModeloT) -> dict[str, Any]:
        """Columnas propias del sucesor más allá del FK, el estado y la fecha."""
        return {}

    async def _ya_tiene_sucesor(self, documento_id: UUID) -> bool:
        """Aprobar dos veces no duplica la cadena.

        Se miran solo los activos: si el sucesor se dio de baja, volver a
        aprobar es la forma de regenerarlo.
        """
        existe = await self.db.scalar(
            select(self.sucesor.id)
            .where(
                getattr(self.sucesor, self.campo_en_sucesor) == documento_id,
                self.sucesor.is_active.is_(True),
            )
            .limit(1)
        )
        return existe is not None

    async def _lineas_de(self, documento_id: UUID) -> list[Any]:
        return list(
            (
                await self.db.execute(
                    select(self.detalle).where(
                        getattr(self.detalle, self.campo_detalle) == documento_id,
                        self.detalle.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )

    async def _copiar_lineas(self, hijo: Any, lineas: list[Any], usuario_id) -> None:
        """Clona las líneas en el sucesor y le deja el total cuadrado."""
        total = Decimal(0)
        for linea in lineas:
            importe = Decimal(linea.cantidad) * self._precio_unitario(linea)
            total += importe
            extra: dict[str, Any] = {}
            if self.sucesor_con_precio:
                extra["precio_unitario"] = self._precio_unitario(linea)
            if self.campo_monto_linea:
                extra[self.campo_monto_linea] = importe
            self.db.add(
                self.detalle_sucesor(
                    **{self.campo_detalle_sucesor: hijo.id},
                    producto_id=linea.producto_id,
                    unidad_medida_id=linea.unidad_medida_id,
                    cantidad=linea.cantidad,
                    **extra,
                    created_by=usuario_id,
                )
            )
        if self.sucesor_con_total:
            hijo.monto_total = total

    def _precio_unitario(self, linea: Any) -> Decimal:
        """El precio de la línea de origen, o cero si no mueve dinero.

        El requerimiento y el pedido llevan cantidades, no importes: cuando el
        sucesor sí tiene precio (la cotización), sus líneas arrancan en cero y
        las llena el proveedor.
        """
        if not self.sucesor_con_precio:
            return Decimal(0)
        return Decimal(getattr(linea, "precio_unitario", 0) or 0)
