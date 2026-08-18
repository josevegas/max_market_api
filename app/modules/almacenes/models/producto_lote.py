import uuid
from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin

ESTADOS = ("disponible", "agotado", "inmovilizado")


class ProductoLote(Base, AuditMixin):
    """Lote concreto que entró por una guía de remisión."""

    __tablename__ = "producto_lote"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('disponible','agotado','inmovilizado')",
            # El nombre lleva el de su propia tabla: copiado de
            # `producto_almacen` chocaba con el de aquella.
            name="chk_producto_lote_estado",
        ),
        UniqueConstraint("producto_id", "codigo_lote", name="uq_producto_lote_codigo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    guia_remision_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        # Faltaba la columna: `ForeignKey("guia_remision")` a secas no apunta
        # a nada.
        ForeignKey("guia_remision.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Sin esto un lote no dice de qué producto es, y no se puede saber qué
    #: caduca ni cuánto stock hay de cada cosa.
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
    # `date.today` sin paréntesis: es la función, y SQLAlchemy la llama en cada
    # INSERT. Con `date.today()` el valor se congelaría al importar el módulo.
    fecha_ingreso: Mapped[date] = mapped_column(
        Date, nullable=False, default=date.today
    )
    cantidad: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    codigo_lote: Mapped[str] = mapped_column(String(30), nullable=False)
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    estado: Mapped[str] = mapped_column(
        String(50), nullable=False, default="disponible"
    )
