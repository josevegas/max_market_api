import uuid

from sqlalchemy import ForeignKey, Integer, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class RequerimientoDetalle(Base, AuditMixin):
    __tablename__ = "requerimiento_detalle"
    __table_args__ = (
        UniqueConstraint(
            "requerimiento_id",
            "producto_id",
            name="uq_requerimiento_detalle_producto",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    requerimiento_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("requerimientos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
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
    cantidad: Mapped[int] = mapped_column(Integer(), nullable=False, default=1)
