from __future__ import annotations

from typing import ClassVar

from app.modules.movimientos.models.cotizacion import Cotizacion
from app.modules.movimientos.models.cotizacion_detalle import CotizacionDetalle
from app.modules.movimientos.services.detalle_con_total import DetalleConTotalService


class CotizacionDetalleService(DetalleConTotalService[CotizacionDetalle]):
    modelo = CotizacionDetalle
    entidad = "Línea de cotización"

    cabecera: ClassVar[type] = Cotizacion
    campo_cabecera: ClassVar[str] = "cotizacion_id"
    #: La línea sí guarda su importe, para poder leerlo sin recalcular.
    campo_monto: ClassVar[str] = "monto_producto"
