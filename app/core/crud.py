"""CRUD genérico para las entidades de catálogo.

Las siete entidades de productos comparten exactamente la misma mecánica
(listar, obtener, crear, actualizar, dar de baja), así que vive una sola vez
acá y cada servicio solo declara su modelo. Cuando una entidad necesite lógica
propia, se sobreescribe el método o se agrega uno nuevo en su servicio.

La baja es **lógica** (`is_active = False`): los catálogos están referenciados
por productos y borrarlos de verdad rompería el histórico.
"""

from __future__ import annotations

from typing import Any, ClassVar, Generic, TypeVar
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


def _sqlstate(exc: Exception) -> str | None:
    """Código SQLSTATE del error, mirando la cadena de excepciones.

    SQLAlchemy envuelve el error del driver, y el driver envuelve el de
    PostgreSQL: el código puede estar en cualquiera de los tres.
    """
    candidatos = (
        getattr(exc, "orig", None),
        getattr(getattr(exc, "orig", None), "__cause__", None),
        exc,
    )
    for candidato in candidatos:
        codigo = getattr(candidato, "sqlstate", None) or getattr(
            candidato, "pgcode", None
        )
        if codigo:
            return str(codigo)
    return None


class CRUDService(Generic[ModeloT]):
    """Operaciones comunes sobre un modelo."""

    modelo: type[ModeloT]
    entidad: str

    #: Campos que no se pueden repetir, con el ámbito en el que aplican:
    #: `{"nombre": "familia_id"}` = el nombre es único dentro de cada familia;
    #: `{"codigo": None}` = el código es único en toda la tabla.
    #: El texto se compara sin distinguir mayúsculas ni espacios al borde, que
    #: es como lo entiende quien carga el catálogo.
    campos_unicos: ClassVar[dict[str, str | None]] = {}

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Lectura ─────────────────────────────────────────────────────────────

    def _con_filtros(
        self, consulta, solo_activos: bool, filtros: dict[str, Any] | None
    ):
        """Las condiciones comunes al listado y al conteo.

        Viven en un solo sitio a propósito: si el `total` se calculara con un
        filtro distinto del de los `items`, la paginación mostraría un número
        de páginas que no corresponde con lo que devuelve.
        """
        if solo_activos:
            consulta = consulta.where(self.modelo.is_active.is_(True))
        for columna, valor in (filtros or {}).items():
            if valor is not None:
                consulta = consulta.where(getattr(self.modelo, columna) == valor)
        return consulta

    async def listar(
        self,
        *,
        solo_activos: bool = True,
        limite: int = 100,
        desplazamiento: int = 0,
        filtros: dict[str, Any] | None = None,
    ) -> list[ModeloT]:
        consulta = self._con_filtros(select(self.modelo), solo_activos, filtros)
        consulta = consulta.limit(limite).offset(desplazamiento)
        return list((await self.db.execute(consulta)).scalars().all())

    async def contar(
        self,
        *,
        solo_activos: bool = True,
        filtros: dict[str, Any] | None = None,
    ) -> int:
        """Cuántos registros cumplen el filtro, sin trocear."""
        consulta = self._con_filtros(
            select(func.count()).select_from(self.modelo), solo_activos, filtros
        )
        return await self.db.scalar(consulta) or 0

    async def obtener(self, registro_id: UUID) -> ModeloT:
        registro = await self.db.get(self.modelo, registro_id)
        if registro is None:
            raise NoEncontradoError(self.entidad, registro_id)
        return registro

    # ── Escritura ───────────────────────────────────────────────────────────

    async def crear(self, datos: BaseModel, usuario_id: UUID | None = None) -> ModeloT:
        registro = await self._crear_sin_guardar(datos, usuario_id)
        await self._guardar(registro)
        return registro

    async def _crear_sin_guardar(
        self, datos: BaseModel, usuario_id: UUID | None = None
    ) -> ModeloT:
        """El alta sin el commit, para poder acompañarla de otros cambios.

        Simétrico de `_aplicar_cambios`, y por el mismo motivo: hay altas que
        arrastran más escrituras y las dos cosas tienen que entrar juntas. Una
        línea de recepción alimenta el stock (ver `stock_service`), y con el
        commit dentro el lote quedaba en una transacción que nadie cerraba.
        """
        valores = datos.model_dump()
        await self._validar_unicidad(valores)
        registro = self.modelo(**valores, created_by=usuario_id)
        self.db.add(registro)
        # `flush` y no `commit`: hace falta que la fila exista para lo que
        # venga colgado de ella, pero la transacción sigue abierta.
        await self._vaciar()
        return registro

    async def actualizar(
        self, registro_id: UUID, datos: BaseModel, usuario_id: UUID | None = None
    ) -> ModeloT:
        registro = await self._aplicar_cambios(registro_id, datos, usuario_id)
        await self._guardar(registro)
        return registro

    async def _aplicar_cambios(
        self, registro_id: UUID, datos: BaseModel, usuario_id: UUID | None = None
    ) -> ModeloT:
        """La edición sin el commit, para poder acompañarla de otros cambios.

        Está separada de `actualizar` porque hay ediciones que arrastran más
        escrituras y las dos cosas tienen que entrar juntas: aprobar un
        documento genera el siguiente de la cadena (ver `generacion.py`). Con el
        commit dentro no había forma de meterlas en la misma transacción, y un
        fallo al generar dejaba el documento aprobado sin sucesor.
        """
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
                await self.db.execute(
                    select(self.modelo.id).where(*condiciones).limit(1)
                )
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
        registro = await self._desactivar_sin_guardar(registro_id, usuario_id)
        await self._guardar(registro)
        return registro

    async def _desactivar_sin_guardar(
        self, registro_id: UUID, usuario_id: UUID | None = None
    ) -> ModeloT:
        """La baja sin el commit. Mismo motivo que `_crear_sin_guardar`."""
        registro = await self.obtener(registro_id)
        registro.is_active = False
        registro.updated_by = usuario_id
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
            await self._traducir_integridad(exc)

    async def _vaciar(self) -> None:
        """`flush` con la misma traducción de errores que el commit.

        El `flush` manda el INSERT sin cerrar la transacción, así que puede
        chocar con las mismas restricciones. Sin pasar por acá salía como un
        500 y encima dejaba la sesión con la transacción abortada.
        """
        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self._traducir_integridad(exc)

    async def _traducir_integridad(self, exc: IntegrityError) -> None:
        """Convierte el error de la base en uno de dominio. Siempre relanza."""
        await self.db.rollback()
        # Se mira el SQLSTATE, no el texto del error: PostgreSQL traduce
        # los mensajes al idioma del servidor ("llave foránea" en un
        # servidor en español), así que buscar "foreign key" no encuentra
        # nada. El código, en cambio, es siempre el mismo.
        codigo = _sqlstate(exc)
        if codigo == "23505":  # unique_violation
            raise ConflictoError(
                f"Ya existe un registro de {self.entidad} con esos datos únicos."
            ) from exc
        if codigo == "23503":  # foreign_key_violation
            raise ReferenciaInvalidaError(
                "Alguna de las referencias enviadas no existe."
            ) from exc
        if codigo in ("23502", "23514"):  # not_null / check_violation
            raise ReferenciaInvalidaError(
                "Los datos enviados no cumplen una restricción de la base."
            ) from exc
        raise exc

    @staticmethod
    def columna(atributo: InstrumentedAttribute) -> str:
        return atributo.key
