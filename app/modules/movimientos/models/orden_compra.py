import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class OrdenCompra(Base, AuditMixin):
    """Lo que se compra de verdad. El proveedor sale de su cotización.

    `proveedor_id` se quitó a propósito: duplicaba `cotizaciones.proveedor_id`
    y podían acabar diciendo cosas distintas. Se llega con
    `orden.cotizacion_id → cotizacion.proveedor_id`.
    """

    __tablename__ = "orden_compra"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    cotizacion_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("cotizaciones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Suma de las líneas, calculada por `OrdenCompraDetalleService`. Arranca
    #: en 0: la orden se crea antes que su detalle.
    monto_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0, server_default="0"
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    estado_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("estados.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
