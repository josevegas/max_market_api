"""Base declarativa común a todos los modelos.

Esquema único: las tablas viven en `public` y no declaran schema.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

#: Nombres predecibles para índices y constraints. Sin esto, PostgreSQL los
#: autogenera y Alembic no sabe cómo referirlos al hacer downgrade.
CONVENCION_NOMBRES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCION_NOMBRES)
