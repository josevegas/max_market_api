from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.unidades.schemas.tabla_equivalencia import (
    TablaEquivalenciaCreate,
    TablaEquivalenciaResponse,
    TablaEquivalenciaUpdate,
)
from app.modules.unidades.services.tabla_equivalencia_service import (
    TablaEquivalenciaService,
)

router = crear_router_crud(
    prefijo="/tablas-equivalencia",
    etiqueta="Tablas de equivalencia",
    servicio=TablaEquivalenciaService,
    schema_create=TablaEquivalenciaCreate,
    schema_update=TablaEquivalenciaUpdate,
    schema_response=TablaEquivalenciaResponse,
    filtros={"unidad_medida_id": UUID},
)
