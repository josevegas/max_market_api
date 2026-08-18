import uuid

from sqlalchemy import String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class TipoMovimiento(Base, AuditMixin):
    __tablename__ = "tipo_movimiento"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    descripcion: Mapped[str] = mapped_column(String(30), nullable=False)
    codigo: Mapped[str] = mapped_column(String(10), nullable=False)
