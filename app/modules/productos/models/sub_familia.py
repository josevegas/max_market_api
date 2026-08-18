from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import AuditMixin

if TYPE_CHECKING:
    from app.modules.productos.models.familia import Familia
    from app.modules.productos.models.producto import Producto


class SubFamilia(Base, AuditMixin):
    __tablename__ = "sub_familias"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    codigo: Mapped[str | None] = mapped_column(String(10), nullable=True)
    familia_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("familias.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    familia: Mapped[Familia] = relationship("Familia", back_populates="sub_familias")
    productos: Mapped[list[Producto]] = relationship(
        "Producto", back_populates="sub_familia"
    )
