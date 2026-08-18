import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class Factura(Base, AuditMixin):
    __tablename__ = "facturas"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    proveedor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("empresa.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    guia_remision_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("guia_remision.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    orden_compra_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("orden_compra.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    monto_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    monto_pago: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    fecha_emicion: Mapped[date] = mapped_column(
        Date, nullable=False, default=date.today
    )
    fecha_vencimiento: Mapped[date] = mapped_column(
        Date, nullable=False, default=date.today
    )
    estado_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("estado.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
