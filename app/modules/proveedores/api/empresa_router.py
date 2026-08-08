"""Endpoints de empresas, incluida el alta asistida por RUC."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.crud_router import a_http, crear_router_crud
from app.core.dependencies import get_db
from app.core.exceptions import ConflictoError, NoEncontradoError
from app.modules.proveedores.schemas.empresa import (
    ConsultaRucResponse,
    EmpresaCreate,
    EmpresaResponse,
    EmpresaUpdate,
)
from app.modules.proveedores.services.empresa_service import (
    EmpresaService,
    ServicioExternoError,
)

router = crear_router_crud(
    prefijo="/empresas",
    etiqueta="Empresas",
    servicio=EmpresaService,
    schema_create=EmpresaCreate,
    schema_update=EmpresaUpdate,
    schema_response=EmpresaResponse,
    filtros={"es_proveedor": bool},
)


@router.get(
    "/ruc/{ruc}",
    response_model=ConsultaRucResponse,
    summary="Consultar un RUC en SUNAT",
    description=(
        "Consulta el RUC contra api.json.pe y devuelve los datos ya "
        "normalizados. No guarda nada: sirve para precargar el formulario."
    ),
)
async def consultar_ruc(ruc: str, db: AsyncSession = Depends(get_db)):
    try:
        return await EmpresaService(db).consultar_ruc(ruc)
    except NoEncontradoError as e:
        raise a_http(e)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ServicioExternoError as e:
        # 502: el fallo es del servicio de terceros, no de quien llama.
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post(
    "/desde-ruc/{ruc}",
    response_model=EmpresaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Dar de alta una empresa desde su RUC",
    description="Consulta SUNAT y crea la empresa con la razón social y la dirección que devuelve.",
)
async def crear_desde_ruc(
    ruc: str,
    es_proveedor: bool = Query(True, description="Marca la empresa como proveedora"),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await EmpresaService(db).crear_desde_ruc(ruc, es_proveedor=es_proveedor)
    except (NoEncontradoError, ConflictoError) as e:
        raise a_http(e)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ServicioExternoError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
