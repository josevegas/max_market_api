import uuid

from sqlalchemy import String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import AuditMixin
from app.modules.unidades.models.tabla_equivalencia import TablaEquivalencia


class UnidadMedida(Base, AuditMixin):
    __tablename__ = "unidades_medida"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    descripcion: Mapped[str] = mapped_column(String(50), nullable=False)
    codigo: Mapped[str] = mapped_column(String(10), nullable=False)

    #: La equivalencia de la unidad, que es una fila aparte por el `UNIQUE` de
    #: `tabla_equivalencia`, pero conceptualmente un atributo suyo: sin ella la
    #: unidad no se puede usar en un movimiento (`conversion.factor_de` corta
    #: con 400). Se carga con `selectin` para que el listado la traiga en una
    #: consulta extra y no una por fila, y sin disparar IO al serializar.
    #:
    #: `viewonly`: las altas y bajas pasan por `UnidadMedidaService`, que las
    #: hace en la misma transacción que la unidad. Escribir por acá saltaría
    #: esa lógica.
    equivalencia: Mapped[TablaEquivalencia | None] = relationship(
        "TablaEquivalencia",
        lazy="selectin",
        uselist=False,
        viewonly=True,
    )

    @property
    def factor_conversion(self) -> int | None:
        """Cuántas unidades mínimas vale una de esta unidad.

        `None` solo en unidades anteriores a que el alta exigiera el factor;
        el formulario ya no permite crearlas así.
        """
        return self.equivalencia.factor_conversion if self.equivalencia else None
