import uuid

from sqlalchemy import ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class Cuenta(Base, AuditMixin):
    __tablename__ = "cuentas"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    numero_cuenta: Mapped[str] = mapped_column(String(20), nullable=False)
    banco_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("bancos.id", ondelete="CASCADE"),
        nullable=False,
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("empresas.id", ondelete="CASCADE"),
        nullable=False,
    )
    tipo_cuenta_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tipo_cuenta.id", ondelete="CASCADE"),
        nullable=False,
    )
    moneda: Mapped[str] = mapped_column(String(10), nullable=False)
