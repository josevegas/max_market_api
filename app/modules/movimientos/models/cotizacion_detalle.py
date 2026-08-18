import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class CotizacionDetalle(Base, AuditMixin):
    """Línea cotizada por un proveedor: producto, cantidad y precio."""

    __tablename__ = "cotizacion_detalle"
    __table_args__ = (
        UniqueConstraint(
            "cotizacion_id", "producto_id", name="uq_cotizacion_detalle_producto"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    #: Faltaba por completo: las líneas no tenían dueño y quedaban huérfanas.
    cotizacion_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("cotizaciones.id", ondelete="CASCADE"),
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
    cantidad: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    precio_unitario: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    #: Derivado (`cantidad * precio_unitario`). Lo calcula el servicio, no el
    #: cliente: así no puede llegar un importe que no cuadre con sus factores.
    monto_producto: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
