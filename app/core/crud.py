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
from sqlalchemy import func, select
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

    #: Campos que no se pueden repetir, con el ámbito en el que aplican:
    #: `{"nombre": "familia_id"}` = el nombre es único dentro de cada familia;
    #: `{"codigo": None}` = el código es único en toda la tabla.
    #: El texto se compara sin distinguir mayúsculas ni espacios al borde, que
    #: es como lo entiende quien carga el catálogo.
    campos_unicos: dict[str, str | None] = {}

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
        valores = datos.model_dump()
        await self._validar_unicidad(valores)
        registro = self.modelo(**valores, created_by=usuario_id)
        self.db.add(registro)
        await self._guardar(registro)
        return registro

    async def actualizar(
        self, registro_id: UUID, datos: BaseModel, usuario_id: UUID | None = None
    ) -> ModeloT:
        registro = await self.obtener(registro_id)
        # `exclude_unset`: un PATCH solo toca lo que el cliente mandó; sin esto
        # los campos omitidos se sobrescribirían con None.
        cambios = datos.model_dump(exclude_unset=True)

        # Al editar hay que mirar el registro completo, no solo lo que llega:
        # cambiar el padre puede volver duplicado un nombre que no lo era.
        estado = {campo: getattr(registro, campo) for campo in self._campos_a_revisar()}
        estado.update(cambios)
        await self._validar_unicidad(estado, excluir_id=registro.id)

        for campo, valor in cambios.items():
            setattr(registro, campo, valor)
        registro.updated_by = usuario_id
        await self._guardar(registro)
        return registro

    # ── Unicidad ────────────────────────────────────────────────────────────

    def _campos_a_revisar(self) -> set[str]:
        campos = set(self.campos_unicos)
        campos.update(a for a in self.campos_unicos.values() if a)
        return campos

    async def _validar_unicidad(
        self, valores: dict[str, Any], excluir_id: UUID | None = None
    ) -> None:
        """Rechaza el alta o la edición si ya existe un registro igual.

        La garantía real son los índices únicos de la BD (dos peticiones a la
        vez pasarían las dos por acá); esta comprobación existe para devolver
        un 409 que diga qué campo está repetido, en vez de un error de
        integridad genérico.
        """
        for campo, ambito in self.campos_unicos.items():
            valor = valores.get(campo)
            if valor is None or (isinstance(valor, str) and not valor.strip()):
                continue  # Los opcionales vacíos no compiten entre sí.

            columna = getattr(self.modelo, campo)
            condiciones = [
                func.lower(func.trim(columna)) == str(valor).strip().lower()
                if isinstance(valor, str)
                else columna == valor
            ]
            if ambito:
                condiciones.append(getattr(self.modelo, ambito) == valores.get(ambito))
            if excluir_id is not None:
                condiciones.append(self.modelo.id != excluir_id)

            existe = (
                await self.db.execute(select(self.modelo.id).where(*condiciones).limit(1))
            ).first()
            if existe:
                donde = " en el mismo ámbito" if ambito else ""
                raise ConflictoError(
                    f"Ya existe {self.entidad} con {campo} '{valor}'{donde}."
                )

    async def desactivar(
        self, registro_id: UUID, usuario_id: UUID | None = None
    ) -> ModeloT:
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
