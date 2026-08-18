from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select

from app.core.crud import CRUDService
from app.modules.unidades.models.tabla_equivalencia import TablaEquivalencia
from app.modules.unidades.models.unidad_medida import UnidadMedida


class UnidadMedidaService(CRUDService[UnidadMedida]):
    """La unidad y su equivalencia se administran juntas.

    `factor_conversion` vive en `tabla_equivalencia` por el `UNIQUE` que impide
    dos factores para la misma unidad, pero para quien usa el sistema es un
    atributo de la unidad: sin él no se la puede usar en un movimiento, porque
    `conversion.factor_de` corta con 400 en vez de asumir 1.

    Por eso las dos filas se escriben en la misma transacción. Con dos altas
    separadas —la unidad por un endpoint y la equivalencia por otro— un fallo
    en la segunda dejaría exactamente la unidad rota que este diseño evita.
    """

    modelo = UnidadMedida
    entidad = "Unidad de medida"
    campos_unicos: ClassVar[dict[str, str | None]] = {
        "descripcion": None,
        "codigo": None,
    }

    async def crear(self, datos: BaseModel, usuario_id: UUID | None = None) -> UnidadMedida:
        valores = datos.model_dump()
        factor = valores.pop("factor_conversion", 1)

        await self._validar_unicidad(valores)
        unidad = self.modelo(**valores, created_by=usuario_id)
        self.db.add(unidad)
        # Flush y no commit: hace falta el id para la equivalencia, pero la
        # transacción tiene que seguir abierta para que las dos filas entren o
        # no entre ninguna.
        await self.db.flush()

        self.db.add(
            TablaEquivalencia(
                unidad_medida_id=unidad.id,
                factor_conversion=factor,
                created_by=usuario_id,
            )
        )
        await self._guardar(unidad)
        return unidad

    async def actualizar(
        self, registro_id: UUID, datos: BaseModel, usuario_id: UUID | None = None
    ) -> UnidadMedida:
        # No se delega en `super()` a propósito: ese commitea al terminar, y
        # entonces la equivalencia quedaría en una transacción aparte.
        cambios = datos.model_dump(exclude_unset=True)
        factor = cambios.pop("factor_conversion", None)

        unidad = await self.obtener(registro_id)

        if cambios:
            # Contra el registro completo, no solo contra lo enviado: un PATCH
            # que manda medio dato puede volver duplicado lo que no lo era.
            estado = {campo: getattr(unidad, campo) for campo in self._campos_a_revisar()}
            estado.update(cambios)
            await self._validar_unicidad(estado, excluir_id=unidad.id)
            for campo, valor in cambios.items():
                setattr(unidad, campo, valor)

        if factor is not None:
            await self._fijar_factor(unidad.id, factor, usuario_id)

        unidad.updated_by = usuario_id
        await self._guardar(unidad)
        return unidad

    async def _fijar_factor(
        self, unidad_id: UUID, factor: int, usuario_id: UUID | None
    ) -> None:
        """Deja la equivalencia de la unidad en `factor`, exista o no.

        Las unidades anteriores a este campo no tienen fila, así que editarlas
        es la vía para completarlas; de ahí que sea un upsert y no un update.
        """
        equivalencia = await self.db.scalar(
            select(TablaEquivalencia).where(
                TablaEquivalencia.unidad_medida_id == unidad_id
            )
        )
        if equivalencia is None:
            self.db.add(
                TablaEquivalencia(
                    unidad_medida_id=unidad_id,
                    factor_conversion=factor,
                    created_by=usuario_id,
                )
            )
            return

        equivalencia.factor_conversion = factor
        equivalencia.updated_by = usuario_id
        # Reactivar si estaba de baja: el `UNIQUE` por unidad impide crear otra
        # al lado, así que sin esto la unidad quedaría sin factor utilizable.
        equivalencia.is_active = True
