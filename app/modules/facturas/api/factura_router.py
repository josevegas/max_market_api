from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.facturas.schemas.factura import (
    FacturaCreate,
    FacturaResponse,
    FacturaUpdate,
)
from app.modules.facturas.services.factura_service import FacturaService

router = crear_router_crud(
    prefijo="/facturas",
    etiqueta="Facturas",
    servicio=FacturaService,
    schema_create=FacturaCreate,
    schema_update=FacturaUpdate,
    schema_response=FacturaResponse,
    filtros={
        "proveedor_id": UUID,
        "orden_compra_id": UUID,
        "guia_remision_id": UUID,
        "estado_id": UUID,
        "serie": str,
        "correlativo": str,
    },
)
