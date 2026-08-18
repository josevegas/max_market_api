import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class Requerimiento(Base, AuditMixin):
    """Lo que un almacén necesita reponer. Cabecera; el qué va en el detalle."""

    __tablename__ = "requerimientos"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    #: Apunta al almacén y no al market: el stock vive en almacenes, y un
    #: market puede tener varios. Sin esto no se sabe dónde entra la
    #: mercadería ni contra qué ficha de `producto_almacen` cuadrarla.
    almacen_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("almacenes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    estado_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("estados.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
