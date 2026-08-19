import uuid
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class VentaDetalle(Base, AuditMixin):
    """Lo que se llevó el cliente, línea a línea.

    La `cantidad` va en la **unidad de venta del producto**, la misma en que
    están los lotes y en la que `producto_almacen.precio_venta_tienda` fija el
    precio. Al ser el mismo terreno no hay conversión de por medio, que es
    justo lo que evita el descuadre que el resto del módulo se ocupa de
    impedir.
    """

    __tablename__ = "venta_detalle"
    __table_args__ = (
        # Igual que en las demás líneas del sistema: un producto aparece una
        # vez por documento. Dos filas del mismo producto harían ambiguo contra
        # qué stock cuadrar lo vendido.
        UniqueConstraint("venta_id", "producto_id", name="uq_venta_detalle_producto"),
        CheckConstraint("cantidad > 0", name="chk_venta_detalle_cantidad_positiva"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    venta_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("ventas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    producto_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("productos.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cantidad: Mapped[int] = mapped_column(Integer(), nullable=False)
    #: Lo pone el servicio desde la ficha del almacén; no se recibe.
    precio_unitario: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0, server_default="0"
    )
    #: `cantidad * precio_unitario`, derivado como en el resto de los detalles.
    monto: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0, server_default="0"
    )


class VentaLote(Base, AuditMixin):
    """De qué lote salió cada unidad vendida.

    Una línea puede consumir varios lotes —se vende 30 y el que vence antes
    solo tiene 12—, así que la correspondencia no cabe en la línea. Sin esta
    tabla no habría forma de **devolver** el stock exactamente a donde estaba
    al anular la venta, y tampoco de responder la pregunta que un market con
    perecibles necesita poder responder: a quién se le vendió tal lote.
    """

    __tablename__ = "venta_lote"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    venta_detalle_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("venta_detalle.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    producto_lote_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("producto_lote.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cantidad: Mapped[int] = mapped_column(Integer(), nullable=False)
