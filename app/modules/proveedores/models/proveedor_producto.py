import uuid

from sqlalchemy import ForeignKey, Integer, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import AuditMixin
from app.modules.productos.models.producto import Producto
from app.modules.proveedores.models.proveedor import Proveedor


class ProveedorProducto(Base, AuditMixin):
    __tablename__ = "proveedor_productos"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    proveedor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("proveedores.id", ondelete="CASCADE"),
        nullable=False,
    )
    producto_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("productos.id", ondelete="CASCADE"),
        nullable=False,
    )
    tiempo_atencion: Mapped[int] = mapped_column(Integer, nullable=False)

    proveedor: Mapped[Proveedor] = relationship("Proveedor", back_populates="productos")
    producto: Mapped[Producto] = relationship("Producto", back_populates="proveedores")
