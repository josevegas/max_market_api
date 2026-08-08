from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import AuditMixin

if TYPE_CHECKING:
    from app.modules.productos.models.producto import Producto
    from app.modules.proveedores.models.empresa import Empresa


class ProveedorProducto(Base, AuditMixin):
    """Qué producto provee qué empresa, y en cuánto tiempo lo atiende."""

    __tablename__ = "proveedor_productos"
    __table_args__ = (
        # Una empresa no puede figurar dos veces como proveedora del mismo
        # producto: sería el mismo dato con dos tiempos de atención.
        UniqueConstraint("empresa_id", "producto_id", name="uq_proveedor_producto"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("empresas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    producto_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("productos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Días que tarda el proveedor en atender un pedido de este producto.
    tiempo_atencion: Mapped[int] = mapped_column(Integer, nullable=False)

    # La clase es `Empresa` (con `es_proveedor`), no `Proveedor`.
    empresa: Mapped[Empresa] = relationship("Empresa", back_populates="productos")
    producto: Mapped[Producto] = relationship("Producto", back_populates="proveedores")
