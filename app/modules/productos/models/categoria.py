from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import AuditMixin

if TYPE_CHECKING:
    from app.modules.productos.models.producto import Producto
    from app.modules.productos.models.sub_categoria import SubCategoria


class Categoria(Base, AuditMixin):
    __tablename__ = "categorias"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    codigo: Mapped[str | None] = mapped_column(String(10), nullable=True)
    sub_familia_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        # RESTRICT y no SET NULL: la columna es obligatoria, así que anularla
        # al borrar la sub familia dejaría la fila en un estado imposible.
        ForeignKey("sub_familias.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    margen_ganancia: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    sub_categorias: Mapped[list[SubCategoria]] = relationship(
        "SubCategoria", back_populates="categoria"
    )
    productos: Mapped[list[Producto]] = relationship(
        "Producto", back_populates="categoria"
    )
