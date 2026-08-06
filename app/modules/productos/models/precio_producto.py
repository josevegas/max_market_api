from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import AuditMixin

if TYPE_CHECKING:
    from app.modules.productos.models.producto import Producto


class PrecioProducto(Base, AuditMixin):
    """Precio de un producto con vigencia.

    Los importes son `Numeric`, no `float`: en coma flotante, sumar precios
    arrastra errores de redondeo que terminan en un total que no cuadra.
    """

    __tablename__ = "precio_producto"
    __table_args__ = (
        CheckConstraint(
            "fecha_fin IS NULL OR fecha_fin >= fecha_inicio",
            name="fecha_fin_posterior",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    producto_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("productos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    precio_compra: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    precio_venta: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    #: Fechas reales, no texto: es lo que permite filtrar por vigencia.
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    #: NULL = vigente hasta nuevo aviso.
    fecha_fin: Mapped[date | None] = mapped_column(Date, nullable=True)

    producto: Mapped[Producto] = relationship("Producto", back_populates="precios")
