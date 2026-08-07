import uuid

from sqlalchemy import String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class Banco(Base, AuditMixin):
    __tablename__ = "bancos"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    razon_social: Mapped[str] = mapped_column(String(100), nullable=False)
    ruc: Mapped[str] = mapped_column(String(11), nullable=False)
    direccion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(15), nullable=True)
    codigo: Mapped[str | None] = mapped_column(String(10), nullable=True)
