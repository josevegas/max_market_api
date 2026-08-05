"""Punto de entrada de la API."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # El pool mantiene conexiones abiertas: cerrarlas al apagar evita que
    # PostgreSQL las acumule entre reinicios en desarrollo.
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    description="API de consumo para el software de Max Market.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/salud", tags=["Infraestructura"])
async def salud() -> dict[str, str]:
    """Chequeo de vida, sin tocar la base de datos."""
    return {"estado": "ok", "app": settings.APP_NAME}
