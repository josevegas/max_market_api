from __future__ import annotations

from app.api.crud_router import crear_router_crud
from app.modules.movimientos.schemas.estado import (
    EstadoCreate,
    EstadoResponse,
    EstadoUpdate,
)
from app.modules.movimientos.services.estado_service import EstadoService

router = crear_router_crud(
    prefijo="/estados",
    etiqueta="Estados",
    servicio=EstadoService,
    schema_create=EstadoCreate,
    schema_update=EstadoUpdate,
    schema_response=EstadoResponse,
    # Filtrar por `codigo` es lo que necesita cualquier cliente que quiera
    # operar la cadena: para aprobar un requerimiento hace falta el id del
    # estado 'APR', y sin este filtro había que traerse el catálogo entero y
    # buscarlo a mano.
    filtros={"codigo": str},
)
