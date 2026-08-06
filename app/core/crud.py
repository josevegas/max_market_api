"""CRUD genérico para las entidades de catálogo.

Las siete entidades de productos comparten exactamente la misma mecánica
(listar, obtener, crear, actualizar, dar de baja), así que vive una sola vez
acá y cada servicio solo declara su modelo. Cuando una entidad necesite lógica
propia, se sobreescribe el método o se agrega uno nuevo en su servicio.

La baja es **lógica** (`is_active = False`): los catálogos están referenciados
por productos y borrarlos de verdad rompería el histórico.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.exceptions import (
    ConflictoError,
    NoEncontradoError,
    ReferenciaInvalidaError,
)
from app.db.base import Base

ModeloT = TypeVar("ModeloT", bound=Base)


class CRUDService(Generic[ModeloT]):
    """Operaciones comunes sobre un modelo."""

    modelo: type[ModeloT]
    entidad: str

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Lectura ─────────────────────────────────────────────────────────────

    async def listar(
        self,
        *,
        solo_activos: bool = True,
        limite: int = 100,
        desplazamiento: int = 0,
        filtros: dict[str, Any] | None = None,
    ) -> list[ModeloT]:
        consulta = select(self.modelo)
        if solo_activos:
            consulta = consulta.where(self.modelo.is_active.is_(True))
        for columna, valor in (filtros or {}).items():
            if valor is not None:
                consulta = consulta.where(getattr(self.modelo, columna) == valor)
        consulta = consulta.limit(limite).offset(desplazamiento)
        return list((await self.db.execute(consulta)).scalars().all())

    async def obtener(self, registro_id: UUID) -> ModeloT:
        registro = await self.db.get(self.modelo, registro_id)
        if registro is None:
            raise NoEncontradoError(self.entidad, registro_id)
        return registro

    # ── Escritura ───────────────────────────────────────────────────────────

    async def crear(self, datos: BaseModel, usuario_id: UUID | None = None) -> ModeloT:
        registro = self.modelo(**datos.model_dump(), created_by=usuario_id)
        self.db.add(registro)
        await self._guardar(registro)
        return registro

    async def actualizar(
        self, registro_id: UUID, datos: BaseModel, usuario_id: UUID | None = None
    ) -> ModeloT:
        registro = await self.obtener(registro_id)
        # `exclude_unset`: un PATCH solo toca lo que el cliente mandó; sin esto
        # los campos omitidos se sobrescribirían con None.
        for campo, valor in datos.model_dump(exclude_unset=True).items():
            setattr(registro, campo, valor)
        registro.updated_by = usuario_id
        await self._guardar(registro)
        return registro

    async def desactivar(self, registro_id: UUID, usuario_id: UUID | None = None) -> ModeloT:
        """Baja lógica: la fila queda, deja de listarse."""
        registro = await self.obtener(registro_id)
        registro.is_active = False
        registro.updated_by = usuario_id
        await self._guardar(registro)
        return registro

    # ── Interno ─────────────────────────────────────────────────────────────

    async def _guardar(self, registro: ModeloT | None = None) -> None:
        """Commit traduciendo los errores de integridad a errores de dominio.

        Sin esto, un SKU repetido o una FK inexistente salen como un 500; con
        esto el cliente recibe 409 o 400 y sabe qué corregir.

        El `refresh` no es opcional: `created_at`/`updated_at` los genera el
        servidor, así que tras el INSERT la instancia no los tiene y leerlos al
        serializar la respuesta dispararía IO fuera del greenlet async.
        """
        try:
            await self.db.commit()
            if registro is not None:
                await self.db.refresh(registro)
        except IntegrityError as exc:
            await self.db.rollback()
            detalle = str(getattr(exc, "orig", exc))
            if "duplicate key" in detalle or "unique" in detalle.lower():
                raise ConflictoError(
                    f"Ya existe un registro de {self.entidad} con esos datos únicos."
                ) from exc
            if "foreign key" in detalle.lower():
                raise ReferenciaInvalidaError(
                    "Alguna de las referencias enviadas no existe."
                ) from exc
            raise

    @staticmethod
    def columna(atributo: InstrumentedAttribute) -> str:
        return atributo.key
