"""Fábrica de routers CRUD.

Las entidades de catálogo exponen los mismos cinco endpoints, así que se
generan desde acá en lugar de repetir 35 handlers idénticos. Cada módulo puede
seguir agregando endpoints propios sobre el router que devuelve esta función
(ver `producto_router`).

Traduce los errores de dominio a HTTP en un solo lugar: los servicios no saben
que existe FastAPI.
"""

# Sin `from __future__ import annotations` a propósito: los handlers se arman
# en runtime y sus anotaciones son variables locales (`schema_create`, etc.).
# Con anotaciones diferidas quedarían como texto y Pydantic no podría
# resolverlas al construir el modelo del endpoint.
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import CRUDService
from app.core.dependencies import get_db
from app.core.exceptions import (
    ConflictoError,
    NoEncontradoError,
    ReferenciaInvalidaError,
)

_CODIGOS = {
    NoEncontradoError: status.HTTP_404_NOT_FOUND,
    ConflictoError: status.HTTP_409_CONFLICT,
    ReferenciaInvalidaError: status.HTTP_400_BAD_REQUEST,
}


def a_http(error: Exception) -> HTTPException:
    """Traduce un error de dominio al HTTP que le corresponde."""
    for tipo, codigo in _CODIGOS.items():
        if isinstance(error, tipo):
            return HTTPException(status_code=codigo, detail=str(error))
    raise error


def crear_router_crud(
    *,
    prefijo: str,
    etiqueta: str,
    servicio: type[CRUDService],
    schema_create: type[BaseModel],
    schema_update: type[BaseModel],
    schema_response: type[BaseModel],
    filtros: dict[str, Any] | None = None,
) -> APIRouter:
    """Router con los cinco endpoints estándar de una entidad.

    `filtros` declara los query params por los que se puede filtrar el listado,
    como ``{"categoria_id": UUID}``.
    """
    router = APIRouter(prefix=prefijo, tags=[etiqueta])
    nombres_filtros = list((filtros or {}).keys())

    @router.get("", response_model=list[schema_response], summary=f"Listar {etiqueta.lower()}")
    async def listar(
        solo_activos: bool = Query(True, description="Excluye los dados de baja"),
        limite: int = Query(100, ge=1, le=500),
        desplazamiento: int = Query(0, ge=0),
        db: AsyncSession = Depends(get_db),
        **kwargs: Any,
    ):
        aplicados = {n: kwargs.get(n) for n in nombres_filtros}
        return await servicio(db).listar(
            solo_activos=solo_activos,
            limite=limite,
            desplazamiento=desplazamiento,
            filtros=aplicados,
        )

    # La firma se reescribe siempre, tenga filtros o no: hay que quitar el
    # `**kwargs` o FastAPI lo toma por un query param llamado "kwargs" y exige
    # que venga en la URL (422 en todos los listados sin filtros).
    import inspect

    firma = inspect.signature(listar)
    parametros = [p for p in firma.parameters.values() if p.name != "kwargs"]
    # Los filtros se agregan acá para que FastAPI los vea como query params
    # normales y los documente en el OpenAPI.
    parametros += [
        inspect.Parameter(
            nombre,
            inspect.Parameter.KEYWORD_ONLY,
            default=Query(None, description=f"Filtrar por {nombre}"),
            annotation=tipo | None,
        )
        for nombre, tipo in (filtros or {}).items()
    ]
    listar.__signature__ = firma.replace(parameters=parametros)

    @router.get(
        "/{registro_id}",
        response_model=schema_response,
        summary=f"Obtener {etiqueta.lower()} por id",
    )
    async def obtener(registro_id: UUID, db: AsyncSession = Depends(get_db)):
        try:
            return await servicio(db).obtener(registro_id)
        except NoEncontradoError as e:
            raise a_http(e)

    @router.post(
        "",
        response_model=schema_response,
        status_code=status.HTTP_201_CREATED,
        summary=f"Crear {etiqueta.lower()}",
    )
    async def crear(datos: schema_create, db: AsyncSession = Depends(get_db)):
        try:
            return await servicio(db).crear(datos)
        except (ConflictoError, ReferenciaInvalidaError) as e:
            raise a_http(e)

    @router.patch(
        "/{registro_id}",
        response_model=schema_response,
        summary=f"Actualizar {etiqueta.lower()}",
    )
    async def actualizar(
        registro_id: UUID, datos: schema_update, db: AsyncSession = Depends(get_db)
    ):
        try:
            return await servicio(db).actualizar(registro_id, datos)
        except (NoEncontradoError, ConflictoError, ReferenciaInvalidaError) as e:
            raise a_http(e)

    @router.delete(
        "/{registro_id}",
        response_model=schema_response,
        summary=f"Dar de baja {etiqueta.lower()}",
        description=(
            "Baja lógica: la fila se conserva y deja de listarse. Los catálogos "
            "están referenciados por productos y borrarlos rompería el histórico."
        ),
    )
    async def desactivar(registro_id: UUID, db: AsyncSession = Depends(get_db)):
        try:
            return await servicio(db).desactivar(registro_id)
        except NoEncontradoError as e:
            raise a_http(e)

    return router
