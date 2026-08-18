import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class Pedido(Base, AuditMixin):
    """Pedido que nace de un requerimiento y sale a cotizar."""

    __tablename__ = "pedidos"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    #: Sin esto un pedido no dice de qué requerimiento sale, y la cadena
    #: almacén → requerimiento → pedido queda cortada.
    requerimiento_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("requerimientos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    estado_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("estados.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
