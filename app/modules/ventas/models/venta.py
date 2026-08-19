import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Date,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class Venta(Base, AuditMixin):
    """El comprobante que el market le emite a un cliente.

    Sale de un **almacén**: es donde están los lotes que se descuentan y la
    ficha que fija el precio. El market se deduce subiendo (`almacen → market`);
    al revés no se podría, porque un market puede tener más de un almacén y
    nada diría de cuál salió la mercadería.
    """

    __tablename__ = "ventas"
    __table_args__ = (
        # La numeración corre por tipo de comprobante: la boleta B001-000001 y
        # la factura F001-000001 conviven, pero dos boletas con el mismo número
        # son la misma venta cargada dos veces.
        UniqueConstraint(
            "tipo_comprobante_id",
            "serie_comprobante",
            "numero_comprobante",
            name="uq_venta_comprobante",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    #: De dónde sale la mercadería. Sin esto no hay contra qué stock descontar
    #: ni de qué ficha tomar el precio.
    almacen_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("almacenes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    #: Serie y número tal como se imprimen, con sus ceros a la izquierda.
    serie_comprobante: Mapped[str] = mapped_column(String(4), nullable=False)
    numero_comprobante: Mapped[str] = mapped_column(String(8), nullable=False)
    #: `RESTRICT` y no `SET NULL`: la columna es obligatoria, así que anularla
    #: al borrar el tipo dejaría la fila en un estado imposible.
    tipo_comprobante_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tipo_comprobante.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    #: Lo suman sus líneas; no se recibe. Nace en cero porque la venta se crea
    #: antes que su detalle.
    monto_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0, server_default="0"
    )
    #: Solo la factura lo exige; la boleta se emite sin identificar al cliente.
    ruc_cliente: Mapped[str | None] = mapped_column(String(11), nullable=True)
    estado_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("estados.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
