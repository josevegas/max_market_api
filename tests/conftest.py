"""Infraestructura de los tests.

Corren contra una base de datos **real** de PostgreSQL (`maxmarket_test_db`),
no contra SQLite ni mocks: el esquema usa UUID nativos, índices funcionales
sobre `lower(trim(...))` y CHECKs propios de PostgreSQL, así que un motor
distinto no probaría lo mismo que corre en producción.

La BD de test se crea si falta y se migra con Alembic, de modo que las
migraciones también quedan verificadas en cada corrida.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

RAIZ = Path(__file__).resolve().parents[1]
NOMBRE_BD_TEST = "maxmarket_test_db"


def _url_de_test() -> str:
    """URL de la BD de test: la misma del `.env` cambiando el nombre."""
    cruda = dotenv_values(RAIZ / ".env").get("DATABASE_URL") or os.environ.get(
        "DATABASE_URL"
    )
    if not cruda:
        raise RuntimeError("No se encontró DATABASE_URL en el .env ni en el entorno")
    return make_url(cruda).set(database=NOMBRE_BD_TEST).render_as_string(
        hide_password=False
    )


# Importante: se fija ANTES de importar la app, que lee la configuración al
# importarse. Si se hiciera después, los tests correrían contra la BD real.
URL_TEST = _url_de_test()
os.environ["DATABASE_URL"] = URL_TEST

TABLAS = [
    "proveedor_productos",
    "cuentas",
    "precio_producto",
    "productos",
    "sub_categorias",
    "categorias",
    "sub_familias",
    "familias",
    "presentaciones",
    "empresas",
    "bancos",
    "tipo_cuenta",
    "markets",
    "sedes",
    "zonas",
]


async def _crear_bd_si_falta() -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    servidor = make_url(URL_TEST).set(database="postgres")
    motor = create_async_engine(servidor, isolation_level="AUTOCOMMIT")
    try:
        async with motor.connect() as conexion:
            existe = (
                await conexion.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :n"),
                    {"n": NOMBRE_BD_TEST},
                )
            ).scalar()
            if not existe:
                await conexion.execute(text(f'CREATE DATABASE "{NOMBRE_BD_TEST}"'))
    finally:
        await motor.dispose()


def _migrar() -> None:
    """Alembic en subproceso: así carga su propio `env.py` sin contaminar el
    grafo de imports de los tests."""
    entorno = os.environ.copy()
    entorno["DATABASE_URL"] = URL_TEST
    resultado = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(RAIZ),
        env=entorno,
        capture_output=True,
        text=True,
        check=False,
    )
    if resultado.returncode != 0:
        raise RuntimeError(
            f"alembic upgrade head falló:\n{resultado.stdout}\n{resultado.stderr}"
        )


@pytest.fixture(scope="session", autouse=True)
def _preparar_bd() -> None:
    asyncio.run(_crear_bd_si_falta())
    _migrar()


@pytest_asyncio.fixture(autouse=True)
async def _limpiar_tablas(_preparar_bd) -> AsyncGenerator[None, None]:
    """Cada test arranca con la base vacía.

    Se limpia ANTES de cada test y no después: así, si uno falla, sus datos
    quedan disponibles para inspeccionarlos.
    """
    from sqlalchemy import text

    from app.db.session import engine

    async with engine.begin() as conexion:
        await conexion.execute(
            text("TRUNCATE TABLE " + ", ".join(TABLAS) + " RESTART IDENTITY CASCADE")
        )
    yield


@pytest_asyncio.fixture
async def cliente() -> AsyncGenerator[httpx.AsyncClient, None]:  # noqa: F821
    """Cliente HTTP contra la app en memoria (sin levantar un servidor)."""
    import httpx
    from httpx import ASGITransport

    from app.main import app

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", timeout=30
    ) as c:
        yield c


@pytest_asyncio.fixture
async def catalogo(_limpiar_tablas, cliente) -> dict[str, str]:
    # Depende de `_limpiar_tablas` a propósito: pytest no garantiza el orden
    # entre una fixture autouse y otra que no la declara, y si el truncado
    # corriera después, esta jerarquía desaparecería antes del test.
    """Jerarquía mínima creada por la API: familia → sub familia → categoría →
    sub categoría, más una presentación. Es lo que casi todo test necesita
    antes de poder crear un producto."""
    familia = (
        await cliente.post(
            "/api/v1/familias", json={"nombre": "Abarrotes", "codigo": "ABA"}
        )
    ).json()
    sub_familia = (
        await cliente.post(
            "/api/v1/sub-familias",
            json={"nombre": "Granos", "codigo": "GRA", "familia_id": familia["id"]},
        )
    ).json()
    categoria = (
        await cliente.post(
            "/api/v1/categorias",
            json={
                "nombre": "Arroz",
                "codigo": "ARR",
                "sub_familia_id": sub_familia["id"],
                "margen_ganancia": "18.50",
            },
        )
    ).json()
    sub_categoria = (
        await cliente.post(
            "/api/v1/sub-categorias",
            json={
                "nombre": "Arroz extra",
                "codigo": "AEX",
                "categoria_id": categoria["id"],
            },
        )
    ).json()
    presentacion = (
        await cliente.post(
            "/api/v1/presentaciones",
            json={"descripcion": "Bolsa 5 kg", "codigo": "B5K"},
        )
    ).json()
    return {
        "familia_id": familia["id"],
        "sub_familia_id": sub_familia["id"],
        "categoria_id": categoria["id"],
        "sub_categoria_id": sub_categoria["id"],
        "presentacion_id": presentacion["id"],
    }


def producto_valido(catalogo: dict[str, str], sku: str = "ARR-EXT-5K") -> dict:
    """Payload de producto con todos los obligatorios.

    El código de barras se deriva del SKU: también es único, así que dejarlo
    fijo haría chocar a cualquier test que cree dos productos.
    """
    return {
        "tipo_producto": "terminado",
        "sku": sku,
        "codigo_barras": f"750{abs(hash(sku)) % 10**10:010d}",
        "descripcion_corta": "Arroz extra 5kg",
        "descripcion_legal": "Arroz extra grano largo 5 kg",
        "descripcion_compra": "Arroz extra 5kg saco",
        "descripcion_web": "Arroz Extra 5 kg",
        **catalogo,
    }
