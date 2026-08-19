from __future__ import annotations

from uuid import UUID

from app.api.crud_router import crear_router_crud
from app.modules.ventas.schemas.venta import (
    TipoComprobanteCreate,
    TipoComprobanteResponse,
    TipoComprobanteUpdate,
    VentaCreate,
    VentaDetalleCreate,
    VentaDetalleResponse,
    VentaDetalleUpdate,
    VentaResponse,
    VentaUpdate,
)
from app.modules.ventas.services.venta_service import (
    TipoComprobanteService,
    VentaDetalleService,
    VentaService,
)

tipos_comprobante_router = crear_router_crud(
    prefijo="/tipos-comprobante",
    etiqueta="Tipos de comprobante",
    servicio=TipoComprobanteService,
    schema_create=TipoComprobanteCreate,
    schema_update=TipoComprobanteUpdate,
    schema_response=TipoComprobanteResponse,
    filtros={"codigo": str},
)

ventas_router = crear_router_crud(
    prefijo="/ventas",
    etiqueta="Ventas",
    servicio=VentaService,
    schema_create=VentaCreate,
    schema_update=VentaUpdate,
    schema_response=VentaResponse,
    filtros={
        "almacen_id": UUID,
        "tipo_comprobante_id": UUID,
        "estado_id": UUID,
        "serie_comprobante": str,
        "numero_comprobante": str,
        "ruc_cliente": str,
    },
)

ventas_detalle_router = crear_router_crud(
    prefijo="/ventas-detalle",
    etiqueta="Detalle de venta",
    servicio=VentaDetalleService,
    schema_create=VentaDetalleCreate,
    schema_update=VentaDetalleUpdate,
    schema_response=VentaDetalleResponse,
    filtros={"venta_id": UUID, "producto_id": UUID},
)
