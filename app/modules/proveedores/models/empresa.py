from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import AuditMixin

if TYPE_CHECKING:
    from app.modules.proveedores.models.proveedor_producto import ProveedorProducto


class Empresa(Base, AuditMixin):
    __tablename__ = "empresas"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    razon_social: Mapped[str] = mapped_column(String(100), nullable=False)
    ruc: Mapped[str] = mapped_column(String(11), nullable=False)
    ubigeo_sunat: Mapped[str] = mapped_column(String(6), nullable=False)
    direccion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(20), nullable=True)
    es_proveedor: Mapped[bool] = mapped_column(Boolean, nullable=False)
    es_ag_retencion: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    es_ag_percepcion: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    estado: Mapped[str] = mapped_column(String(30), nullable=False)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)

    #: Productos que provee, cuando `es_proveedor`. Es la contraparte de
    #: `ProveedorProducto.empresa`: sin ella los mappers no configuran.
    productos: Mapped[list[ProveedorProducto]] = relationship(
        "ProveedorProducto", back_populates="empresa", cascade="all, delete-orphan"
    )
