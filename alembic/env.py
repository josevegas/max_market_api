"""Entorno de Alembic.

La URL sale del `.env` (una sola fuente de verdad, y `alembic.ini` no lleva
credenciales) y el `target_metadata` apunta a la `Base` de la aplicación, que
es lo que habilita `--autogenerate`.

Uso::

    alembic revision --autogenerate -m "descripción"
    alembic upgrade head
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import settings
from app.db.base import Base
from app.db.models import *

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Modo offline: genera el SQL sin conectarse a la base."""
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _incluir_objeto(objeto, nombre, tipo_, reflejado, comparado_con) -> bool:
    """Deja fuera del autogenerado los índices únicos `uq_*`.

    Son índices funcionales (`lower(trim(...))`) y parciales, creados con SQL
    en sus migraciones y no declarados en `Base.metadata`. Sin esta exclusión,
    `--autogenerate` los ve como sobrantes y **propone borrarlos**: ya pasó una
    vez y dejó el catálogo sin protección contra duplicados.
    """
    if tipo_ == "index" and (nombre or "").startswith("uq_"):
        return False
    return True


def _ejecutar_migraciones(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=_incluir_objeto,
        # Detecta también los cambios de tipo de columna, que por defecto
        # pasan desapercibidos al autogenerar.
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(_ejecutar_migraciones)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
