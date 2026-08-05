"""Dependencias de FastAPI."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Sesión de base de datos por request; se cierra al terminar."""
    async with AsyncSessionLocal() as session:
        yield session
