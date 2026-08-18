import uuid

from sqlalchemy import ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class Almacen(Base, AuditMixin):
    """Almacén físico, dependiente de un market."""

    __tablename__ = "almacenes"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    market_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        # La tabla es `markets`, en plural (ver `Market.__tablename__`).
        ForeignKey("markets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nombre: Mapped[str] = mapped_column(String(50), nullable=False)
    codigo: Mapped[str] = mapped_column(String(10), nullable=False)
