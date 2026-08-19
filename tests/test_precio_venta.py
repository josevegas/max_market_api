"""El precio de venta lo calcula el servidor, no el que carga el precio.

    precio_venta = (precio_compra / IGV * (1 + margen/100) + monto_POS) * IGV

El precio de compra viene con IGV, así que se le saca para trabajar sobre el
valor, se aplica el margen de la categoría del producto, se suma el recargo de
punto de venta y recién ahí se vuelve a gravar.

La fórmula se prueba aparte de la API: es una función pura, y probarla por HTTP
obligaría a mover la configuración para cada caso. Por la API se prueba el
cableado —que el margen salga de la categoría del producto y que editar el
precio de compra recalcule— con la configuración por defecto.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.productos.services.calculo_precio import precio_de_venta
from tests.conftest import producto_valido

BASE = "/api/v1"

IGV = Decimal("1.18")

#: El margen que la fixture `catalogo` le pone a la categoría.
MARGEN_FIXTURE = Decimal("18.50")


# ===================== La fórmula =====================


@pytest.mark.parametrize(
    ("compra", "margen", "pos", "esperado"),
    [
        # Sin recargo el IGV se cancela: sacarlo y volver a ponerlo deja el
        # precio de compra multiplicado por el margen.
        ("118.00", "18.50", "0", "139.83"),
        # El caso que se conversó: 118 de compra, 18.5% de margen y 1 de POS.
        ("118.00", "18.50", "1.00", "141.01"),
        # Margen cero: se vende a lo que costó, más el recargo.
        ("100.00", "0", "0", "100.00"),
        ("100.00", "0", "2.00", "102.36"),
        # Un producto regalado sigue costando el recargo de la caja.
        ("0", "18.50", "1.00", "1.18"),
    ],
)
def test_la_formula(compra, margen, pos, esperado):
    assert precio_de_venta(
        Decimal(compra), Decimal(margen), IGV, Decimal(pos)
    ) == Decimal(esperado)


def test_se_redondea_una_sola_vez_al_final():
    """Redondear cada paso arrastraría el error hasta el precio.

    12.30 con 18.5% da 14.5755 exacto: el medio centavo sube, no baja, porque
    el dinero se redondea `HALF_UP` y no con el "al par" de Python.
    """
    assert precio_de_venta(
        Decimal("12.30"), MARGEN_FIXTURE, IGV, Decimal("0")
    ) == Decimal("14.58")


def test_el_margen_es_porcentaje_no_factor():
    """18.50 es 18.5%, no 1850%. Es lo que dice la columna de la categoría, y
    tomarlo como factor daría un precio quince veces mayor."""
    calculado = precio_de_venta(Decimal("100.00"), Decimal("18.50"), IGV, Decimal("0"))

    assert calculado == Decimal("118.50")
    assert calculado < Decimal("200.00")


# ===================== El cableado, por la API =====================


async def _producto(cliente, catalogo, sku="ARR-EXT-5K") -> str:
    r = await cliente.post(f"{BASE}/productos", json=producto_valido(catalogo, sku))
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_el_precio_de_venta_lo_pone_el_servidor(cliente, catalogo):
    producto = await _producto(cliente, catalogo)

    r = await cliente.post(
        f"{BASE}/precios",
        json={
            "producto_id": producto,
            "precio_compra": "12.30",
            "fecha_inicio": "2026-01-01",
        },
    )

    assert r.status_code == 201, r.text
    assert r.json()["precio_venta"] == "14.58"


async def test_el_precio_de_venta_enviado_se_ignora(cliente, catalogo):
    """Igual que `monto_total` en la orden de compra: el que manda es el
    cálculo, no el cliente."""
    producto = await _producto(cliente, catalogo)

    r = await cliente.post(
        f"{BASE}/precios",
        json={
            "producto_id": producto,
            "precio_compra": "12.30",
            "precio_venta": "999.00",
            "fecha_inicio": "2026-01-01",
        },
    )

    assert r.status_code == 201, r.text
    assert r.json()["precio_venta"] == "14.58"


async def test_el_margen_sale_de_la_categoria_del_producto(cliente, catalogo):
    """Dos productos con el mismo costo y distinta categoría valen distinto."""
    otra = (
        await cliente.post(
            f"{BASE}/categorias",
            json={
                "nombre": "Premium",
                "codigo": "PRE",
                "sub_familia_id": catalogo["sub_familia_id"],
                "margen_ganancia": "40.00",
            },
        )
    ).json()["id"]
    barato = await _producto(cliente, catalogo, "ARR-001")
    caro = await _producto(
        cliente, {**catalogo, "categoria_id": otra, "sub_categoria_id": None}, "ARR-002"
    )

    precios = {}
    for etiqueta, producto in (("barato", barato), ("caro", caro)):
        r = await cliente.post(
            f"{BASE}/precios",
            json={
                "producto_id": producto,
                "precio_compra": "100.00",
                "fecha_inicio": "2026-01-01",
            },
        )
        assert r.status_code == 201, r.text
        precios[etiqueta] = r.json()["precio_venta"]

    assert precios == {"barato": "118.50", "caro": "140.00"}


async def test_cambiar_el_precio_de_compra_recalcula_el_de_venta(cliente, catalogo):
    """Corregir lo que costó no puede dejar el precio al público colgado del
    valor anterior."""
    producto = await _producto(cliente, catalogo)
    precio = (
        await cliente.post(
            f"{BASE}/precios",
            json={
                "producto_id": producto,
                "precio_compra": "100.00",
                "fecha_inicio": "2026-01-01",
            },
        )
    ).json()["id"]

    r = await cliente.patch(
        f"{BASE}/precios/{precio}", json={"precio_compra": "200.00"}
    )

    assert r.status_code == 200, r.text
    assert r.json()["precio_venta"] == "237.00"


async def test_editar_solo_la_vigencia_no_mueve_el_precio(cliente, catalogo):
    """El recálculo sale del precio de compra: tocar las fechas no lo cambia."""
    producto = await _producto(cliente, catalogo)
    precio = (
        await cliente.post(
            f"{BASE}/precios",
            json={
                "producto_id": producto,
                "precio_compra": "100.00",
                "fecha_inicio": "2026-01-01",
            },
        )
    ).json()["id"]

    r = await cliente.patch(
        f"{BASE}/precios/{precio}", json={"fecha_fin": "2026-12-31"}
    )

    assert r.status_code == 200, r.text
    assert r.json()["precio_venta"] == "118.50"
