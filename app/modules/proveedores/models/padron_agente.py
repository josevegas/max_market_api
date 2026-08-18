"""Espejo local de los padrones de agentes de retención y percepción de SUNAT.

SUNAT publica dos ZIP con los agentes **vigentes**, así que la pertenencia al
padrón es el dato: si el RUC está, la empresa es agente hoy. No hay columna de
exclusión, y por eso cada sincronización reemplaza la tabla entera en lugar de
ir añadiendo: una empresa excluida desaparece del archivo, y sumar filas nunca
lo detectaría.

Las tablas no llevan `AuditMixin` a propósito. Son un reflejo de una fuente
externa que se regenera completo; una baja lógica acá no significaría nada y
`created_by` no tiene autor humano.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

#: Valores admitidos en `PadronAgente.tipo`.
TIPO_RETENCION = "retencion"
TIPO_PERCEPCION = "percepcion"


class PadronAgente(Base):
    """Una línea del padrón: qué RUC es agente de qué, y desde cuándo."""

    __tablename__ = "padron_agentes"
    __table_args__ = (
        # El mismo RUC puede ser agente de retención y de percepción a la vez,
        # pero no puede figurar dos veces en el mismo padrón.
        UniqueConstraint("ruc", "tipo", name="uq_padron_agente"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    #: Se consulta por RUC en cada alta de empresa, de ahí el índice.
    ruc: Mapped[str] = mapped_column(String(11), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(12), nullable=False)
    #: "A partir del" que trae el archivo. Informativo: el archivo ya solo
    #: lista vigentes, así que no hace falta filtrar por fecha.
    a_partir_de: Mapped[date | None] = mapped_column(Date, nullable=True)
    resolucion: Mapped[str | None] = mapped_column(String(60), nullable=True)


class PadronSincronizacion(Base):
    """Registro de cada corrida, para saber cuándo se verificó por última vez."""

    __tablename__ = "padron_sincronizaciones"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    ejecutada_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    filas_retencion: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filas_percepcion: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Cuántas empresas cambiaron de condición en la reconciliación.
    empresas_actualizadas: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    #: Mensaje del fallo cuando `ok` es falso.
    detalle: Mapped[str | None] = mapped_column(Text, nullable=True)
