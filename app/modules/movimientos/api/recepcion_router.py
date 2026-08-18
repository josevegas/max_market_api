from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.movimientos.schemas.recepcion import (
    RecepcionCreate,
    RecepcionResponse,
    RecepcionUpdate,
)
from app.modules.movimientos.services.recepcion_service import RecepcionService

router = crear_router_crud(
    prefijo="/recepciones",
    etiqueta="Recepciones",
    servicio=RecepcionService,
    schema_create=RecepcionCreate,
    schema_update=RecepcionUpdate,
    schema_response=RecepcionResponse,
    filtros={
        "guia_remision_id": UUID,
        "orden_compra_id": UUID,
        "almacen_id": UUID,
        "estado_id": UUID,
    },
)
