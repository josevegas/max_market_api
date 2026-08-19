import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
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


class Factura(Base, AuditMixin):
    """Lo que el proveedor cobra por una orden de compra.

    Es el documento del proveedor, no nuestro: por eso lleva su serie y su
    correlativo, y por eso su `monto_total` no tiene que coincidir con el de la
    orden —entregas parciales, fletes y ajustes hacen que casi nunca coincida—.
    La diferencia se informa al consultarla; no se bloquea.
    """

    __tablename__ = "facturas"
    __table_args__ = (
        # El mismo número de dos proveedores distintos es normal; repetido del
        # mismo proveedor es la misma factura cargada dos veces.
        UniqueConstraint(
            "proveedor_id", "serie", "correlativo", name="uq_factura_numero"
        ),
        CheckConstraint(
            "fecha_vencimiento >= fecha_emision",
            name="chk_factura_vencimiento_posterior",
        ),
        # Pagar más de lo facturado no es un pago: es un error de carga.
        CheckConstraint(
            "monto_pago <= monto_total",
            name="chk_factura_pago_no_supera_total",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    #: La tabla es `empresas`, en plural (ver `Empresa.__tablename__`).
    proveedor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("empresas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Serie y correlativo del comprobante, tal como vienen impresos. Van
    #: como texto y no como número: el correlativo lleva ceros a la izquierda
    #: y "00001234" no es lo mismo que 1234 a la hora de cruzarlo con SUNAT.
    serie: Mapped[str] = mapped_column(String(4), nullable=False)
    correlativo: Mapped[str] = mapped_column(String(8), nullable=False)
    #: Opcional: el proveedor puede facturar sin haber emitido guía, o
    #: facturar varias guías juntas.
    guia_remision_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("guia_remision.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    orden_compra_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("orden_compra.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    monto_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    #: Cuánto de esa factura ya se pagó. Arranca en cero salvo que se registre
    #: una factura ya cancelada.
    monto_pago: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    fecha_emision: Mapped[date] = mapped_column(
        Date, nullable=False, default=date.today
    )
    fecha_vencimiento: Mapped[date] = mapped_column(
        Date, nullable=False, default=date.today
    )
    #: La tabla es `estados`, en plural (ver `Estado.__tablename__`).
    estado_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("estados.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
