"""Endpoints del padrón de agentes de retención y percepción.

La sincronización periódica la dispara `python -m app.jobs.sincronizar_padron`
desde el programador de tareas; este endpoint existe para forzarla a mano y
para sembrar el padrón la primera vez.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.modules.proveedores.models.padron_agente import (
    TIPO_PERCEPCION,
    TIPO_RETENCION,
)
from app.modules.proveedores.schemas.padron_agente import (
    EstadoPadronResponse,
    ResumenSincronizacionResponse,
)
from app.modules.proveedores.services.padron_agentes import (
    PadronAgentesService,
    PadronError,
)

router = APIRouter(prefix="/padron-agentes", tags=["Padrón de agentes"])


@router.post(
    "/sincronizar",
    response_model=ResumenSincronizacionResponse,
    summary="Descargar los padrones de SUNAT y reconciliar las empresas",
    description=(
        "Reemplaza el padrón guardado con lo que publica SUNAT y actualiza "
        "`es_ag_retencion`/`es_ag_percepcion` de todas las empresas. Tarda unos "
        "segundos: son dos descargas externas."
    ),
)
async def sincronizar(db: AsyncSession = Depends(get_db)):
    try:
        return await PadronAgentesService(db).sincronizar()
    except PadronError as e:
        # 502: el fallo es de la fuente externa, no de quien llama.
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.get(
    "/estado",
    response_model=EstadoPadronResponse,
    summary="Cuándo se verificó el padrón por última vez",
)
async def estado(db: AsyncSession = Depends(get_db)):
    servicio = PadronAgentesService(db)
    conteos = await servicio.conteos()
    ultima = await servicio.ultima_sincronizacion()
    return EstadoPadronResponse(
        tiene_datos=not await servicio.esta_vacio(),
        agentes_retencion=conteos.get(TIPO_RETENCION, 0),
        agentes_percepcion=conteos.get(TIPO_PERCEPCION, 0),
        ultima_sincronizacion=ultima.ejecutada_at if ultima else None,
        ultima_ok=ultima.ok if ultima else None,
        ultimo_detalle=ultima.detalle if ultima else None,
    )
