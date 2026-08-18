import uuid

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class TablaEquivalencia(Base, AuditMixin):
    """Cuántas unidades mínimas vale una unidad: UND → 1, CAJA12 → 12."""

    __tablename__ = "tabla_equivalencia"
    __table_args__ = (
        # Sin esto una unidad podría tener dos factores y la conversión
        # dejaría de ser determinista.
        UniqueConstraint("unidad_medida_id", name="uq_tabla_equivalencia_unidad"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    unidad_medida_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("unidades_medida.id"),
        nullable=False,
        index=True,
    )
    factor_conversion: Mapped[int] = mapped_column(Integer(), nullable=False, default=1)
