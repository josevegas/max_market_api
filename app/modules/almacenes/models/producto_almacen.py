import uuid
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin

#: Estados que admite la ficha. El CHECK de la base y el `Literal` del schema
#: salen de acá, para que no haya dos listas que se puedan desincronizar.
ESTADOS = ("disponible", "agotado", "inmovilizado")


class ProductoAlmacen(Base, AuditMixin):
    """Ficha de un producto en un almacén: mínimos, máximos y precio de tienda."""

    __tablename__ = "producto_almacen"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('disponible','agotado','inmovilizado')",
            name="chk_producto_almacen_estado",
        ),
        # Un producto no puede tener dos fichas en el mismo almacén: serían dos
        # precios y dos mínimos para lo mismo.
        UniqueConstraint("almacen_id", "producto_id", name="uq_producto_almacen"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    almacen_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("almacenes.id", ondelete="CASCADE"),
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
    stock_minimo: Mapped[int] = mapped_column(Integer(), nullable=False, default=1)
    stock_maximo: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    precio_venta_tienda: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    estado: Mapped[str] = mapped_column(
        String(50), nullable=False, default="disponible"
    )
