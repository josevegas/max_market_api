"""Almacenes, unidades de medida y la ficha producto-almacén.

La jerarquía completa es zona → sede → market → almacén. La ficha cruza
almacén, producto y unidad de medida, y no puede repetirse: un producto tiene
un único precio y un único mínimo en cada almacén.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.conftest import producto_valido

BASE = "/api/v1"


async def _crear_almacen(cliente, nombre="Central", codigo="ALM1") -> str:
    zona = (
        await cliente.post(f"{BASE}/zonas", json={"nombre": "Norte", "codigo": "NOR"})
    ).json()["id"]
    sede = (
        await cliente.post(
            f"{BASE}/sedes",
            json={"zona_id": zona, "nombre": "Lima", "codigo": "LIM"},
        )
    ).json()["id"]
    market = (
        await cliente.post(
            f"{BASE}/markets",
            json={"sede_id": sede, "nombre": "Market 1", "codigo": "MK1"},
        )
    ).json()["id"]
    r = await cliente.post(
        f"{BASE}/almacenes",
        json={"market_id": market, "nombre": nombre, "codigo": codigo},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _crear_unidad(cliente, descripcion="Unidad", codigo="UND") -> str:
    r = await cliente.post(
        f"{BASE}/unidades-medida",
        json={"descripcion": descripcion, "codigo": codigo},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _crear_producto(cliente, catalogo, sku="ARR-EXT-5K") -> str:
    r = await cliente.post(f"{BASE}/productos", json=producto_valido(catalogo, sku))
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ===================== Unidades de medida =====================


async def test_crear_unidad_de_medida(cliente):
    r = await cliente.post(
        f"{BASE}/unidades-medida", json={"descripcion": "Kilogramo", "codigo": "KG"}
    )

    assert r.status_code == 201
    assert r.json()["codigo"] == "KG"


async def test_codigo_de_unidad_repetido_es_409(cliente):
    await _crear_unidad(cliente, "Kilogramo", "KG")

    r = await cliente.post(
        f"{BASE}/unidades-medida", json={"descripcion": "Otra", "codigo": "kg"}
    )

    assert r.status_code == 409


async def test_factor_de_conversion_debe_ser_al_menos_uno(cliente):
    unidad = await _crear_unidad(cliente)

    r = await cliente.post(
        f"{BASE}/tablas-equivalencia",
        json={"unidad_medida_id": unidad, "factor_conversion": 0},
    )

    assert r.status_code == 422


# ===================== Almacenes =====================


async def test_crear_almacen_bajo_un_market(cliente):
    almacen = await _crear_almacen(cliente)

    r = await cliente.get(f"{BASE}/almacenes/{almacen}")

    assert r.status_code == 200
    assert r.json()["nombre"] == "Central"


async def test_almacen_con_market_inexistente_es_400(cliente):
    r = await cliente.post(
        f"{BASE}/almacenes",
        json={"market_id": str(uuid4()), "nombre": "Huérfano", "codigo": "HUE"},
    )

    assert r.status_code == 400


async def test_patch_parcial_de_almacen(cliente):
    almacen = await _crear_almacen(cliente)

    r = await cliente.patch(f"{BASE}/almacenes/{almacen}", json={"nombre": "Anexo"})

    assert r.status_code == 200, r.text
    assert r.json()["nombre"] == "Anexo"
    assert r.json()["codigo"] == "ALM1"


async def test_patch_con_null_en_campo_obligatorio_es_422(cliente):
    almacen = await _crear_almacen(cliente)

    r = await cliente.patch(f"{BASE}/almacenes/{almacen}", json={"codigo": None})

    assert r.status_code == 422


# ===================== Ficha producto-almacén =====================


async def test_crear_ficha_de_producto_en_almacen(cliente, catalogo):
    almacen = await _crear_almacen(cliente)
    unidad = await _crear_unidad(cliente)
    producto = await _crear_producto(cliente, catalogo)

    r = await cliente.post(
        f"{BASE}/productos-almacen",
        json={
            "almacen_id": almacen,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "stock_minimo": 10,
            "stock_maximo": 100,
            "precio_venta_tienda": "12.50",
            "estado": "disponible",
        },
    )

    assert r.status_code == 201, r.text
    assert r.json()["precio_venta_tienda"] == "12.50"
    assert r.json()["estado"] == "disponible"


async def test_el_producto_no_se_repite_en_el_mismo_almacen(cliente, catalogo):
    almacen = await _crear_almacen(cliente)
    unidad = await _crear_unidad(cliente)
    producto = await _crear_producto(cliente, catalogo)
    ficha = {
        "almacen_id": almacen,
        "producto_id": producto,
        "unidad_medida_id": unidad,
        "precio_venta_tienda": "12.50",
    }

    assert (
        await cliente.post(f"{BASE}/productos-almacen", json=ficha)
    ).status_code == 201

    r = await cliente.post(f"{BASE}/productos-almacen", json=ficha)

    assert r.status_code == 409


@pytest.mark.parametrize("estado", ["vendido", "DISPONIBLE", "", "otro"])
async def test_estado_no_admitido_es_422(cliente, catalogo, estado):
    almacen = await _crear_almacen(cliente)
    unidad = await _crear_unidad(cliente)
    producto = await _crear_producto(cliente, catalogo)

    r = await cliente.post(
        f"{BASE}/productos-almacen",
        json={
            "almacen_id": almacen,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "precio_venta_tienda": "12.50",
            "estado": estado,
        },
    )

    assert r.status_code == 422


async def test_stock_maximo_menor_que_el_minimo_es_422(cliente, catalogo):
    almacen = await _crear_almacen(cliente)
    unidad = await _crear_unidad(cliente)
    producto = await _crear_producto(cliente, catalogo)

    r = await cliente.post(
        f"{BASE}/productos-almacen",
        json={
            "almacen_id": almacen,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "stock_minimo": 50,
            "stock_maximo": 10,
            "precio_venta_tienda": "12.50",
        },
    )

    assert r.status_code == 422


async def test_precio_negativo_es_422(cliente, catalogo):
    almacen = await _crear_almacen(cliente)
    unidad = await _crear_unidad(cliente)
    producto = await _crear_producto(cliente, catalogo)

    r = await cliente.post(
        f"{BASE}/productos-almacen",
        json={
            "almacen_id": almacen,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "precio_venta_tienda": "-1.00",
        },
    )

    assert r.status_code == 422


async def test_filtrar_fichas_por_almacen_y_estado(cliente, catalogo):
    almacen = await _crear_almacen(cliente)
    unidad = await _crear_unidad(cliente)
    uno = await _crear_producto(cliente, catalogo, "SKU-UNO")
    dos = await _crear_producto(cliente, catalogo, "SKU-DOS")

    base = {
        "almacen_id": almacen,
        "unidad_medida_id": unidad,
        "precio_venta_tienda": "1.00",
    }
    ficha_uno = (
        await cliente.post(
            f"{BASE}/productos-almacen",
            json={**base, "producto_id": uno, "estado": "disponible"},
        )
    ).json()["id"]
    await cliente.post(
        f"{BASE}/productos-almacen",
        json={**base, "producto_id": dos, "estado": "agotado"},
    )

    r = await cliente.get(
        f"{BASE}/productos-almacen",
        params={"almacen_id": almacen, "estado": "disponible"},
    )

    assert [f["id"] for f in r.json()["items"]] == [ficha_uno]
