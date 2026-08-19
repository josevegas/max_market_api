import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class Recepcion(Base, AuditMixin):
    """La entrada física de la mercadería al almacén.

    Es el documento que cierra la cadena: al registrarse, la guía pasa a
    `RECEPCIONADO` y el resto de la cadena a `ATENDIDO` (ver
    `RecepcionService`).
    """

    __tablename__ = "recepcion"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    guia_remision_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("guia_remision.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    #: `SET NULL` y no `CASCADE`: anular la factura no borra la recepción. La
    #: mercadería entró igual, y perder ese registro por un problema de
    #: facturación dejaría el stock sin el documento que lo respalda.
    factura_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("facturas.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    #: Redundante con `guia_remision.orden_compra_id` cuando la recepción viene
    #: de una guía, pero la recepción también puede registrarse contra la orden
    #: directamente. Si llegan las dos, el servicio comprueba que coincidan.
    orden_compra_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("orden_compra.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    almacen_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("almacenes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    estado_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("estados.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Como el resto de documentos de la cadena: sin fecha no se puede ordenar
    #: ni cuadrar una recepción con el periodo en que entró la mercadería.
    fecha: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    observaciones: Mapped[str | None] = mapped_column(String(500), nullable=True)
