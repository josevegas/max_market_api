"""La cadena de compras y las reglas que la hacen avanzar.

    requerimiento → pedido → cotización → orden de compra → guía de remisión

Cada eslabón solo nace si el anterior está **aprobado**. Sin esto, la cadena
existía como referencias entre tablas pero no como proceso: se podía emitir una
orden de compra contra una cotización que nadie había mirado, y el `estado_id`
de cada documento era un adorno que no condicionaba nada.

La regla vive acá y no en cada servicio porque los cuatro casos son el mismo:
mirar el estado del padre y cortar si no está aprobado. Repetirla cuatro veces
significa que un día tres digan una cosa y la cuarta otra.
"""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import CRUDService, ModeloT
from app.core.exceptions import ConflictoError, ReferenciaInvalidaError
from app.modules.movimientos.constantes import CODIGO_APROBADO
from app.modules.movimientos.models.estado import Estado


async def codigo_de_estado(db: AsyncSession, estado_id: UUID | None) -> str | None:
    """El `codigo` del estado, o `None` si el documento no lo tiene."""
    if estado_id is None:
        return None
    return await db.scalar(select(Estado.codigo).where(Estado.id == estado_id))


async def id_de_codigo(db: AsyncSession, codigo: str) -> UUID:
    """El id del estado canónico, o un 400 que dice cuál falta.

    Puede faltar de verdad: la migración lo siembra, pero `estados` admite baja
    lógica y nada impide desactivarlo. Mejor un mensaje que nombre el código que
    un `NOT NULL` en `estado_id` a mitad del guardado.
    """
    estado_id = await db.scalar(
        select(Estado.id).where(Estado.codigo == codigo, Estado.is_active.is_(True))
    )
    if estado_id is None:
        raise ReferenciaInvalidaError(
            f"No existe el estado con código '{codigo}'. Es uno de los estados "
            "que la cadena de compras necesita para operar."
        )
    return estado_id


class DocumentoEncadenadoService(CRUDService[ModeloT]):
    """CRUD de un documento que solo puede nacer de un padre aprobado."""

    #: Modelo del documento anterior en la cadena (Requerimiento, Pedido...).
    padre: ClassVar[type]
    #: Columna de este documento que apunta al padre.
    campo_padre: ClassVar[str]
    #: Cómo se llama el padre en el mensaje de error.
    entidad_padre: ClassVar[str]

    async def crear(self, datos: BaseModel, usuario_id: UUID | None = None) -> ModeloT:
        await self._exigir_padre_aprobado(datos.model_dump().get(self.campo_padre))
        return await super().crear(datos, usuario_id)

    async def actualizar(
        self, registro_id: UUID, datos: BaseModel, usuario_id: UUID | None = None
    ) -> ModeloT:
        """Reapuntar el documento revalida; tocar la fecha no.

        Solo se mira si el `*_id` del padre viene en el PATCH. Sin esto quedaba
        un hueco evidente: crear contra un padre aprobado y reapuntar después a
        uno pendiente, con lo que la validación del alta no serviría de nada.
        """
        cambios = datos.model_dump(exclude_unset=True)
        if self.campo_padre in cambios:
            await self._exigir_padre_aprobado(cambios[self.campo_padre])
        return await super().actualizar(registro_id, datos, usuario_id)

    async def _exigir_padre_aprobado(self, padre_id: UUID | None) -> None:
        if padre_id is None:
            return
        padre = await self.db.get(self.padre, padre_id)
        if padre is None:
            raise ReferenciaInvalidaError(f"{self.entidad_padre} {padre_id} no existe.")
        codigo = await codigo_de_estado(self.db, padre.estado_id)
        if codigo != CODIGO_APROBADO:
            raise ConflictoError(
                f"{self.entidad_padre} {padre_id} no está aprobado "
                f"(estado '{codigo or 'sin estado'}'). "
                f"Apruébelo antes de generar {self.entidad.lower()}."
            )
