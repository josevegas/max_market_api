import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import AuditMixin


class Producto(Base, AuditMixin):
    __tablename__ = "productos"
    __table_args__ = {"schema": "public"}

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(255), nullable=True)
    categoria_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("categorias.id", ondelete="CASCADE"),
        nullable=False,
    )
    sub_categoria_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sub_categorias.id", ondelete="CASCADE"),
        nullable=True,
    )
    familia_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("familias.id", ondelete="CASCADE"),
        nullable=False,
    )
    sub_familia_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sub_familias.id", ondelete="CASCADE"),
        nullable=False,
    )
    sku: Mapped[str] = mapped_column(String(15), nullable=False)
    codigo_barras: Mapped[str] = mapped_column(String(50), nullable=True)

    categoria = relationship("Categoria", back_populates="productos")
    sub_categoria = relationship("SubCategoria", back_populates="productos")
    familia = relationship("Familia", back_populates="productos")
    sub_familia = relationship("SubFamilia", back_populates="productos")
