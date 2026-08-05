import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import AuditMixin


class PrecioProducto(Base, AuditMixin):
    __tablename__ = "precio_producto"
    __table_args__ = {"schema": "public"}

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    producto_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("productos.id", ondelete="CASCADE"),
        nullable=False,
    )
    precio_compra: Mapped[float] = mapped_column(nullable=False)
    precio_venta: Mapped[float] = mapped_column(nullable=False)
    fecha_inicio: Mapped[str] = mapped_column(String(10), nullable=False)
    fecha_fin: Mapped[str] = mapped_column(String(10), nullable=True)

    producto = relationship("Producto", back_populates="precios")
