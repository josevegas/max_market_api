import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class Cotizacion(Base, AuditMixin):
    __tablename__ = "cotizaciones"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    pedido_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pedidos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    proveedor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("empresas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    monto_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    tiempo_atencion: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    #: Días de crédito que ofrece el proveedor: 0 es contado, 30 es a 30 días.
    #:
    #: NOT NULL con default 0 y no nullable a propósito: el comparativo puntúa
    #: este campo, y un nulo tendría que decidir si vale como contado o como
    #: "sin dato". Con 0 la cotización que nadie completó queda en el peor caso
    #: para el proveedor, que es lo contrario de premiar el dato faltante.
    condicion_pago_dias: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=0, server_default=text("0")
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    estado_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("estados.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
