import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
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

ESTADOS = ("disponible", "agotado", "inmovilizado")


class ProductoLote(Base, AuditMixin):
    """Lote concreto que entró por una guía de remisión."""

    __tablename__ = "producto_lote"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('disponible','agotado','inmovilizado')",
            # El nombre lleva el de su propia tabla: copiado de
            # `producto_almacen` chocaba con el de aquella.
            name="chk_producto_lote_estado",
        ),
        # El almacén entra en la clave: el mismo lote del proveedor puede
        # quedar repartido en dos almacenes, y esas son dos pilas físicas
        # distintas, no un choque de códigos.
        UniqueConstraint(
            "almacen_id",
            "producto_id",
            "codigo_lote",
            name="uq_producto_lote_codigo",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    #: Dónde está la mercadería. Sin esto el stock no se puede atribuir a un
    #: almacén, y el `stock_minimo` contra el que hay que compararlo vive en
    #: `producto_almacen`, que sí es por almacén.
    almacen_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("almacenes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Opcional: una recepción contra orden de compra directa no tiene guía
    #: (el proveedor entregó sin papel previo) y su stock también es stock.
    guia_remision_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        # Faltaba la columna: `ForeignKey("guia_remision")` a secas no apunta
        # a nada.
        ForeignKey("guia_remision.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    #: Sin esto un lote no dice de qué producto es, y no se puede saber qué
    #: caduca ni cuánto stock hay de cada cosa.
    producto_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("productos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # `date.today` sin paréntesis: es la función, y SQLAlchemy la llama en cada
    # INSERT. Con `date.today()` el valor se congelaría al importar el módulo.
    fecha_ingreso: Mapped[date] = mapped_column(
        Date, nullable=False, default=date.today
    )
    cantidad: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    #: Lo que costó una unidad **de venta** de este lote. La línea de recepción
    #: cobra por su propia unidad (por caja, por ejemplo), así que se convierte
    #: al guardarlo: sin eso, comparar el costo de un lote en cajas contra otro
    #: en unidades sueltas no significaría nada.
    precio_compra: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0, server_default="0"
    )
    codigo_lote: Mapped[str] = mapped_column(String(30), nullable=False)
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    dias_alerta_vencimiento: Mapped[int | None] = mapped_column(
        Integer(), nullable=True
    )
    estado: Mapped[str] = mapped_column(
        String(50), nullable=False, default="disponible"
    )
