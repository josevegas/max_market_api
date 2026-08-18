import uuid
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class RecepcionDetalle(Base, AuditMixin):
    """Lo que entró de verdad, línea a línea.

    Guarda tres cantidades y no una: lo que la guía decía (`cantidad_esperada`),
    lo que se aceptó (`cantidad_ingresada`) y lo que se devolvió al proveedor
    (`cantidad_devuelta`). Con una sola no se distingue "no lo trajeron" de
    "lo trajeron mal", que es justo lo que se le reclama al proveedor.
    """

    __tablename__ = "recepcion_detalle"
    __table_args__ = (
        # Igual que en las demás líneas de la cadena: un producto aparece una
        # vez por documento. Dos filas del mismo producto harían ambiguo contra
        # cuál cuadrar lo recibido.
        UniqueConstraint(
            "recepcion_id",
            "producto_id",
            name="uq_recepcion_detalle_producto",
        ),
        CheckConstraint(
            "cantidad_esperada >= 0 AND cantidad_ingresada >= 0 "
            "AND cantidad_devuelta >= 0",
            name="cantidades_no_negativas",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    #: Faltaba: sin esto la línea no dice de qué recepción es y no hay forma de
    #: listar el detalle de una recepción ni de sumarlo.
    recepcion_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("recepcion.id", ondelete="CASCADE"),
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
    cantidad_esperada: Mapped[int] = mapped_column(
        Integer(), nullable=False, server_default="0"
    )
    cantidad_ingresada: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=0, server_default="0"
    )
    cantidad_devuelta: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=0, server_default="0"
    )
    precio_unitario: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    #: Opcional: no todo lo que se recibe se maneja por lotes, y el schema ya
    #: lo daba por opcional. Antes la columna era NOT NULL y el alta sin lote
    #: salía como un 400 de integridad sin decir qué faltaba.
    codigo_lote: Mapped[str | None] = mapped_column(String(30), nullable=True)
