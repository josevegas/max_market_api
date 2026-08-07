"""Punto de entrada de la API."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

# El navegador bloquea las llamadas del frontend si el origen no está
# declarado acá. Va antes de montar el router para que también cubra las
# respuestas de error y las peticiones preflight (OPTIONS).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Infraestructura"], include_in_schema=False)
async def raiz() -> dict[str, str]:
    """Orientación mínima: sin esto, entrar por la raíz devuelve un 404 seco
    que parece que la API no levantó."""
    return {
        "app": settings.APP_NAME,
        "version": app.version,
        "documentacion": "/docs",
        "api": settings.API_V1_PREFIX,
        "salud": "/salud",
    }


@app.get("/salud", tags=["Infraestructura"])
async def salud() -> dict[str, str]:
    """Chequeo de vida, sin tocar la base de datos."""
    return {"estado": "ok", "app": settings.APP_NAME}
