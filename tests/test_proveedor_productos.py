"""Tests de la asignación de productos a proveedores.

El `tiempo_atencion` son días desde el pedido: es lo que decide a quién comprar
cuando varios proveedores ofrecen el mismo producto.
"""

from __future__ import annotations

from uuid import uuid4

import pytest_asyncio

from tests.conftest import producto_valido

BASE = "/api/v1"


@pytest_asyncio.fixture
async def proveedor(_limpiar_tablas, cliente) -> str:
    r = await cliente.post(
        f"{BASE}/empresas",
        json={
            "razon_social": "Distribuidora Andina",
            "ruc": "20111111111",
            "ubigeo_sunat": "150137",
            "estado": "ACTIVO",
            "es_proveedor": True,
        },
    )
    return r.json()["id"]


@pytest_asyncio.fixture
async def producto(cliente, catalogo) -> str:
    r = await cliente.post(f"{BASE}/productos", json=producto_valido(catalogo))
    return r.json()["id"]


# ===================== Asignación =====================


async def test_asignar_un_producto(cliente, proveedor, producto):
    r = await cliente.put(
        f"{BASE}/empresas/{proveedor}/productos/{producto}",
        json={"producto_id": producto, "tiempo_atencion": 5},
    )

    assert r.status_code == 200
    assert r.json()["tiempo_atencion"] == 5
    assert r.json()["empresa_id"] == proveedor


async def test_reasignar_actualiza_el_tiempo_en_vez_de_fallar(
    cliente, proveedor, producto
):
    """Volver a asignar algo que ya se distribuye es corregir el plazo, no un
    error: quien mantiene el catálogo no tiene que consultar antes."""
    url = f"{BASE}/empresas/{proveedor}/productos/{producto}"
    primera = await cliente.put(
        url, json={"producto_id": producto, "tiempo_atencion": 5}
    )
    segunda = await cliente.put(
        url, json={"producto_id": producto, "tiempo_atencion": 2}
    )

    assert segunda.status_code == 200
    assert segunda.json()["tiempo_atencion"] == 2
    # Es la misma fila, no una nueva.
    assert segunda.json()["id"] == primera.json()["id"]


async def test_entrega_inmediata_es_valida(cliente, proveedor, producto):
    r = await cliente.put(
        f"{BASE}/empresas/{proveedor}/productos/{producto}",
        json={"producto_id": producto, "tiempo_atencion": 0},
    )

    assert r.status_code == 200


async def test_tiempo_negativo_es_422(cliente, proveedor, producto):
    r = await cliente.put(
        f"{BASE}/empresas/{proveedor}/productos/{producto}",
        json={"producto_id": producto, "tiempo_atencion": -1},
    )

    assert r.status_code == 422


async def test_no_se_asignan_productos_a_quien_no_es_proveedor(cliente, producto):
    """Sin esta validación, el catálogo de compras se llenaría de empresas a
    las que no se les puede comprar."""
    cliente_no_proveedor = (
        await cliente.post(
            f"{BASE}/empresas",
            json={
                "razon_social": "Cliente Final",
                "ruc": "20222222222",
                "ubigeo_sunat": "150137",
                "estado": "ACTIVO",
                "es_proveedor": False,
            },
        )
    ).json()["id"]

    r = await cliente.put(
        f"{BASE}/empresas/{cliente_no_proveedor}/productos/{producto}",
        json={"producto_id": producto, "tiempo_atencion": 3},
    )

    assert r.status_code == 400
    assert "proveedora" in r.json()["detail"]


async def test_empresa_inexistente_es_404(cliente, producto):
    r = await cliente.put(
        f"{BASE}/empresas/{uuid4()}/productos/{producto}",
        json={"producto_id": producto, "tiempo_atencion": 3},
    )

    assert r.status_code == 404


async def test_producto_inexistente_es_404(cliente, proveedor):
    r = await cliente.put(
        f"{BASE}/empresas/{proveedor}/productos/{uuid4()}",
        json={"producto_id": str(uuid4()), "tiempo_atencion": 3},
    )

    assert r.status_code == 404


# ===================== Alta masiva =====================


async def test_asignar_varios_de_una_vez(cliente, proveedor, catalogo):
    otro = (
        await cliente.post(
            f"{BASE}/productos", json=producto_valido(catalogo, sku="ARR-002")
        )
    ).json()["id"]
    uno = (
        await cliente.post(
            f"{BASE}/productos", json=producto_valido(catalogo, sku="ARR-001")
        )
    ).json()["id"]

    r = await cliente.post(
        f"{BASE}/empresas/{proveedor}/productos",
        json={
            "asignaciones": [
                {"producto_id": uno, "tiempo_atencion": 3},
                {"producto_id": otro, "tiempo_atencion": 7},
            ]
        },
    )

    assert r.status_code == 201
    assert len(r.json()) == 2


async def test_si_un_producto_no_existe_no_se_guarda_ninguno(
    cliente, proveedor, producto
):
    """La carga no debe quedar a medias."""
    r = await cliente.post(
        f"{BASE}/empresas/{proveedor}/productos",
        json={
            "asignaciones": [
                {"producto_id": producto, "tiempo_atencion": 3},
                {"producto_id": str(uuid4()), "tiempo_atencion": 7},
            ]
        },
    )

    assert r.status_code == 404
    catalogo_proveedor = (
        await cliente.get(f"{BASE}/empresas/{proveedor}/productos")
    ).json()
    assert catalogo_proveedor["items"] == []


async def test_lista_vacia_es_422(cliente, proveedor):
    r = await cliente.post(
        f"{BASE}/empresas/{proveedor}/productos", json={"asignaciones": []}
    )

    assert r.status_code == 422


# ===================== Consultas =====================


async def test_catalogo_del_proveedor_resuelve_el_producto(
    cliente, proveedor, producto
):
    """Devuelve SKU y descripción: quien lo consulta necesita leerlo, no
    cruzar ids a mano."""
    await cliente.put(
        f"{BASE}/empresas/{proveedor}/productos/{producto}",
        json={"producto_id": producto, "tiempo_atencion": 4},
    )

    r = await cliente.get(f"{BASE}/empresas/{proveedor}/productos")

    assert r.status_code == 200
    fila = r.json()["items"][0]
    assert fila["sku"] == "ARR-EXT-5K"
    assert fila["descripcion_corta"] == "Arroz extra 5kg"
    assert fila["tiempo_atencion"] == 4


async def test_el_catalogo_se_ordena_por_tiempo_de_atencion(
    cliente, proveedor, catalogo
):
    lento = (
        await cliente.post(
            f"{BASE}/productos", json=producto_valido(catalogo, sku="LENTO")
        )
    ).json()["id"]
    rapido = (
        await cliente.post(
            f"{BASE}/productos", json=producto_valido(catalogo, sku="RAPIDO")
        )
    ).json()["id"]
    await cliente.put(
        f"{BASE}/empresas/{proveedor}/productos/{lento}",
        json={"producto_id": lento, "tiempo_atencion": 15},
    )
    await cliente.put(
        f"{BASE}/empresas/{proveedor}/productos/{rapido}",
        json={"producto_id": rapido, "tiempo_atencion": 2},
    )

    r = await cliente.get(f"{BASE}/empresas/{proveedor}/productos")

    assert [f["sku"] for f in r.json()["items"]] == ["RAPIDO", "LENTO"]


async def test_proveedores_de_un_producto_del_mas_rapido_al_mas_lento(
    cliente, producto, proveedor
):
    otro = (
        await cliente.post(
            f"{BASE}/empresas",
            json={
                "razon_social": "Mayorista Express",
                "ruc": "20333333333",
                "ubigeo_sunat": "150137",
                "estado": "ACTIVO",
                "es_proveedor": True,
            },
        )
    ).json()["id"]
    await cliente.put(
        f"{BASE}/empresas/{proveedor}/productos/{producto}",
        json={"producto_id": producto, "tiempo_atencion": 10},
    )
    await cliente.put(
        f"{BASE}/empresas/{otro}/productos/{producto}",
        json={"producto_id": producto, "tiempo_atencion": 3},
    )

    r = await cliente.get(f"{BASE}/productos/{producto}/proveedores")

    assert r.status_code == 200
    assert [p["razon_social"] for p in r.json()["items"]] == [
        "Mayorista Express",
        "Distribuidora Andina",
    ]
    assert r.json()["items"][0]["tiempo_atencion"] == 3


async def test_proveedor_mas_rapido(cliente, producto, proveedor):
    await cliente.put(
        f"{BASE}/empresas/{proveedor}/productos/{producto}",
        json={"producto_id": producto, "tiempo_atencion": 6},
    )

    r = await cliente.get(f"{BASE}/productos/{producto}/proveedor-mas-rapido")

    assert r.status_code == 200
    assert r.json()["razon_social"] == "Distribuidora Andina"


async def test_producto_sin_proveedores_devuelve_nulo(cliente, producto):
    r = await cliente.get(f"{BASE}/productos/{producto}/proveedor-mas-rapido")

    assert r.status_code == 200
    assert r.json() is None


# ===================== Baja =====================


async def test_quitar_del_catalogo_es_baja_logica(cliente, proveedor, producto):
    await cliente.put(
        f"{BASE}/empresas/{proveedor}/productos/{producto}",
        json={"producto_id": producto, "tiempo_atencion": 4},
    )

    r = await cliente.delete(f"{BASE}/empresas/{proveedor}/productos/{producto}")

    assert r.status_code == 200
    assert r.json()["is_active"] is False
    assert (await cliente.get(f"{BASE}/empresas/{proveedor}/productos")).json()[
        "items"
    ] == []


async def test_reasignar_despues_de_la_baja_lo_reactiva(cliente, proveedor, producto):
    """No debe chocar con el UNIQUE de la fila que quedó dada de baja."""
    url = f"{BASE}/empresas/{proveedor}/productos/{producto}"
    await cliente.put(url, json={"producto_id": producto, "tiempo_atencion": 4})
    await cliente.delete(url)

    r = await cliente.put(url, json={"producto_id": producto, "tiempo_atencion": 9})

    assert r.status_code == 200
    assert r.json()["is_active"] is True
    assert r.json()["tiempo_atencion"] == 9


async def test_quitar_algo_no_asignado_es_404(cliente, proveedor, producto):
    r = await cliente.delete(f"{BASE}/empresas/{proveedor}/productos/{producto}")

    assert r.status_code == 404
