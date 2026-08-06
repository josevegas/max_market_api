from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import AuditMixin

if TYPE_CHECKING:
    from app.modules.productos.models.categoria import Categoria
    from app.modules.productos.models.familia import Familia
    from app.modules.productos.models.precio_producto import PrecioProducto
    from app.modules.productos.models.presentacion import Presentacion
    from app.modules.productos.models.sub_categoria import SubCategoria
    from app.modules.productos.models.sub_familia import SubFamilia


class Producto(Base, AuditMixin):
    __tablename__ = "productos"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    tipo_producto: Mapped[str] = mapped_column(String(20), nullable=False)
    categoria_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("categorias.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sub_categoria_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sub_categorias.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    familia_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("familias.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sub_familia_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sub_familias.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    presentacion_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("presentaciones.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    #: Breve descripción del producto, para comprobante de compra.
    descripcion_corta: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Descripción legal del producto, para comprobante de compra.
    descripcion_legal: Mapped[str] = mapped_column(String(100), nullable=False)
    #: Descripción del producto para la compra, para ordenes de compra y guias de remisión.
    descripcion_compra: Mapped[str] = mapped_column(String(100), nullable=False)
    #: Descripción del producto para la venta, para ordenes de venta y guias de remisión.
    descripcion_web: Mapped[str] = mapped_column(String(100), nullable=False)
    #: Único: es el identificador con el que opera el negocio.
    sku: Mapped[str] = mapped_column(
        String(15), nullable=False, unique=True, index=True
    )
    codigo_barras: Mapped[str | None] = mapped_column(String(50), nullable=True)

    categoria: Mapped[Categoria] = relationship("Categoria", back_populates="productos")
    sub_categoria: Mapped[SubCategoria | None] = relationship(
        "SubCategoria", back_populates="productos"
    )
    presentacion: Mapped[Presentacion | None] = relationship(
        "Presentacion", back_populates="productos"
    )
    familia: Mapped[Familia] = relationship("Familia", back_populates="productos")
    sub_familia: Mapped[SubFamilia] = relationship(
        "SubFamilia", back_populates="productos"
    )
    #: Historial de precios. `delete-orphan`: un precio sin producto no
    #: significa nada, a diferencia del catálogo, que sí es independiente.
    precios: Mapped[list[PrecioProducto]] = relationship(
        "PrecioProducto",
        back_populates="producto",
        cascade="all, delete-orphan",
        order_by="PrecioProducto.fecha_inicio",
    )
