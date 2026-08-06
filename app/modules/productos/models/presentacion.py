from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import AuditMixin

if TYPE_CHECKING:
    from app.modules.productos.models.producto import Producto


class Presentacion(Base, AuditMixin):
    __tablename__ = "presentaciones"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    descripcion: Mapped[str] = mapped_column(String(150), nullable=False)
    codigo: Mapped[str | None] = mapped_column(String(10), nullable=True)

    productos: Mapped[list[Producto]] = relationship(
        "Producto", back_populates="presentacion"
    )
