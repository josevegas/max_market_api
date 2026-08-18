import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class OrdenCompraDetalle(Base, AuditMixin):
    """Línea de la orden: lo que realmente se compra.

    Tiene líneas propias y no hereda las de la cotización porque la orden
    puede aprobar solo parte de lo cotizado o ajustar cantidades, y porque es
    contra esto contra lo que luego se cuadra la guía de remisión.
    """

    __tablename__ = "orden_compra_detalle"
    __table_args__ = (
        UniqueConstraint(
            "orden_compra_id", "producto_id", name="uq_orden_compra_detalle_producto"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    orden_compra_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("orden_compra.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    producto_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("productos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    unidad_medida_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("unidades_medida.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cantidad: Mapped[int] = mapped_column(Integer(), nullable=False, default=1)
    precio_unitario: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
