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

import httpx
import pytest
import pytest_asyncio
from dotenv import dotenv_values
from httpx import ASGITransport
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
    return (
        make_url(cruda)
        .set(database=NOMBRE_BD_TEST)
        .render_as_string(hide_password=False)
    )


# Importante: se fija ANTES de importar la app, que lee la configuración al
# importarse. Si se hiciera después, los tests correrían contra la BD real.
URL_TEST = _url_de_test()
os.environ["DATABASE_URL"] = URL_TEST

TABLAS = [
    "venta_lote",
    "venta_detalle",
    "ventas",
    "tipo_comprobante",
    "recepcion_detalle",
    "recepcion",
    "facturas",
    "guia_remision_detalle",
    "producto_lote",
    "orden_compra_detalle",
    "guia_remision",
    "orden_compra",
    "cotizacion_detalle",
    "cotizaciones",
    "pedido_detalle",
    "pedidos",
    "requerimiento_detalle",
    "requerimientos",
    "estados",
    "producto_almacen",
    "almacenes",
    "tabla_equivalencia",
    "unidades_medida",
    "padron_agentes",
    "padron_sincronizaciones",
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


async def _soltar_conexiones_colgadas(engine) -> None:
    """Corta las conexiones a la BD de test que quedaron dentro de una
    transacción abierta.

    `TRUNCATE` pide `AccessExclusiveLock` sobre cada tabla. Una conexión
    `idle in transaction` sigue sosteniendo los locks de lectura que tomó, así
    que las dos se esperan y PostgreSQL corta la suite con un deadlock —y los
    fallos aparecen en tests que no tienen nada que ver con la causa—.

    Esas conexiones son siempre basura. La suite corre en un solo proceso y de
    a un test por vez —se comprobó muestreando `pg_stat_activity`: nunca hay
    más de una conexión viva—, así que en este punto, con el pool propio ya
    cerrado, cualquier otra conexión a la BD de test sobra: quedó de una
    corrida interrumpida o de una sesión que no se devolvió al pool. No se
    filtra por `state` porque la que bloquea no siempre está ociosa; a veces
    está a mitad de una consulta, y esa es justamente la que traba el
    `TRUNCATE`.

    El precio de equivocarse es bajo y el de no hacerlo, alto: si alguien
    corriera dos suites a la vez contra la misma base se cortarían entre sí,
    pero eso ya estaba roto —se truncan las tablas la una a la otra—.

    Va en su **propia** conexión, que se abre y se cierra antes de que exista
    la del `TRUNCATE`. Hacerlo dentro de esa misma transacción se veía correcto
    —`pid <> pg_backend_pid()` excluye la propia— pero terminaba matando la
    conexión que estaba por truncar: el `TRUNCATE` moría con "connection was
    closed in the middle of operation". Si la conexión a proteger todavía no
    existe, no hay forma de matarla.

    Si el usuario de la base no tiene permiso para señalar backends, se sigue
    igual: es una limpieza defensiva, no un requisito para correr los tests.
    """
    import contextlib

    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    with contextlib.suppress(SQLAlchemyError):
        async with engine.connect() as conexion:
            await conexion.execute(
                text(
                    """
                    SELECT pg_terminate_backend(pid)
                      FROM pg_stat_activity
                     WHERE datname = current_database()
                       AND pid <> pg_backend_pid()
                    """
                )
            )
    # La conexión que acaba de usarse vuelve al pool, y las que se cortaron
    # pueden haber dejado ahí sockets muertos: se vacía otra vez para que el
    # `TRUNCATE` estrene una conexión sana.
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _limpiar_tablas(_preparar_bd) -> AsyncGenerator[None, None]:
    """Cada test arranca con la base vacía, salvo los estados canónicos.

    Se limpia ANTES de cada test y no después: así, si uno falla, sus datos
    quedan disponibles para inspeccionarlos.

    `estados` se vuelve a sembrar tras el truncado porque la cadena de compras
    los da por existentes: los siembra la migración, y sin ellos ningún test
    podría pasar de un requerimiento a un pedido. Es el mismo estado en que
    queda una base recién migrada.
    """
    from sqlalchemy import text

    from app.db.session import engine
    from app.modules.movimientos.constantes import ESTADOS_CANONICOS

    # El pool propio se cierra antes de truncar: son conexiones nuestras y
    # devolverlas es gratis.
    await engine.dispose()
    await _soltar_conexiones_colgadas(engine)

    async with engine.begin() as conexion:
        # Si aun así algo bloquea, es mejor fallar en cinco segundos con un
        # error que nombra el lock que quedarse esperando: el deadlock salía
        # como fallos repartidos por archivos que no tenían nada que ver.
        await conexion.execute(text("SET LOCAL lock_timeout = '5s'"))
        await conexion.execute(
            text("TRUNCATE TABLE " + ", ".join(TABLAS) + " RESTART IDENTITY CASCADE")
        )
        await conexion.execute(
            text("INSERT INTO estados (descripcion, codigo) VALUES (:d, :c)"),
            [{"d": d, "c": c} for d, c in ESTADOS_CANONICOS],
        )
    yield


@pytest_asyncio.fixture
async def cliente(_limpiar_tablas) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Cliente HTTP contra la app en memoria (sin levantar un servidor).

    Depende de `_limpiar_tablas` por el mismo motivo que `catalogo`: pytest no
    garantiza el orden entre una fixture autouse y otra que no la declara, así
    que el truncado podía correr después de que el test ya hubiera creado sus
    datos. Con pocos tests casi nunca pasaba; al crecer la suite empezó a
    aparecer como filas que se creaban con 201 y al request siguiente ya no
    existían.
    """
    # `app` se importa acá y no arriba: al importarse lee la configuración, y
    # `DATABASE_URL` se fija más arriba en este mismo módulo. `httpx` no tiene
    # esa restricción y va con el resto de imports, que además es lo que hace
    # falta para poder anotar el tipo de retorno.
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
    # `unidad_compra` y `unidad_venta` son obligatorias al crear un producto,
    # así que la jerarquía mínima ya no puede quedarse en el catálogo: sin una
    # unidad de medida no se puede dar de alta ninguno. Se usa la misma para
    # comprar y vender; el test que necesite distinguirlas crea la suya.
    # El código es `UBASE` y no `UND` para no chocar con las unidades que
    # crean por su cuenta los tests de movimientos y de equivalencias.
    unidad = (
        await cliente.post(
            "/api/v1/unidades-medida",
            json={
                "descripcion": "Unidad base",
                "codigo": "UBASE",
                "factor_conversion": 1,
            },
        )
    ).json()
    return {
        "familia_id": familia["id"],
        "sub_familia_id": sub_familia["id"],
        "categoria_id": categoria["id"],
        "sub_categoria_id": sub_categoria["id"],
        "presentacion_id": presentacion["id"],
        "unidad_compra": unidad["id"],
        "unidad_venta": unidad["id"],
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
