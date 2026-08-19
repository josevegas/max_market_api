"""Cadena de compras: requerimiento → pedido → cotización → orden → guía → lote.

Lo que se comprueba de verdad acá es que la cadena **cierra**: que desde un
almacén se llega al producto que pidió, y desde el lote recibido se vuelve al
proveedor que lo trajo. Sin eso, los documentos son cabeceras sueltas.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.movimientos.constantes import CODIGO_APROBADO
from tests.conftest import producto_valido

BASE = "/api/v1"


async def _estado(cliente, codigo=CODIGO_APROBADO) -> str:
    """El id de un estado canónico, que ya viene sembrado.

    Antes cada test creaba su propio estado; ahora los cuatro que la cadena
    reconoce los siembra la migración, y crearlos otra vez chocaría con la
    unicidad de `codigo`. Por defecto devuelve el aprobado: es el único desde
    el que la cadena avanza, así que es lo que casi todo test necesita.
    """
    r = await cliente.get(f"{BASE}/estados", params={"codigo": codigo})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items, f"falta el estado canónico '{codigo}'"
    return items[0]["id"]


async def _almacen(cliente) -> str:
    zona = (
        await cliente.post(f"{BASE}/zonas", json={"nombre": "Norte", "codigo": "NOR"})
    ).json()["id"]
    sede = (
        await cliente.post(
            f"{BASE}/sedes", json={"zona_id": zona, "nombre": "Lima", "codigo": "LIM"}
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
        json={"market_id": market, "nombre": "Central", "codigo": "ALM1"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _almacen_de_la_cadena(cliente) -> str:
    """El almacén que ya creó la cadena.

    `_almacen` no se puede llamar dos veces en el mismo test: zona, sede y
    market tienen código único y el segundo intento choca con un 409 que no
    tiene nada que ver con lo que se está probando.
    """
    items = (await cliente.get(f"{BASE}/almacenes")).json()["items"]
    assert items, "la cadena tiene que haber creado el almacén"
    return items[0]["id"]


async def _unidad(cliente, descripcion="Unidad", codigo="UND", factor=1) -> str:
    """Unidad con su equivalencia registrada.

    Sin equivalencia no se puede convertir a unidad mínima y la validación de
    guía contra lotes corta con un 400, así que va siempre junta. Antes eso
    eran dos altas encadenadas acá; ahora el `factor_conversion` viaja en el
    alta de la unidad y la API escribe las dos filas en una transacción.
    """
    r = await cliente.post(
        f"{BASE}/unidades-medida",
        json={
            "descripcion": descripcion,
            "codigo": codigo,
            "factor_conversion": factor,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _producto(cliente, catalogo, sku="ARR-EXT-5K") -> str:
    return (
        await cliente.post(f"{BASE}/productos", json=producto_valido(catalogo, sku))
    ).json()["id"]


async def _proveedor(cliente, ruc="20552103816") -> str:
    r = await cliente.post(
        f"{BASE}/empresas",
        json={
            "razon_social": "PROVEEDORA S.A.C.",
            "ruc": ruc,
            "ubigeo_sunat": "150101",
            "estado": "ACTIVO",
            "es_proveedor": True,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ===================== La cadena cierra =====================


async def test_del_almacen_al_lote_recibido(cliente, catalogo):
    """El recorrido completo, que es lo que antes no se podía expresar."""
    estado = await _estado(cliente)
    almacen = await _almacen(cliente)
    unidad = await _unidad(cliente)
    producto = await _producto(cliente, catalogo)
    proveedor = await _proveedor(cliente)

    # 1. El almacén pide reponer un producto
    req = (
        await cliente.post(
            f"{BASE}/requerimientos",
            json={"almacen_id": almacen, "estado_id": estado},
        )
    ).json()["id"]
    r = await cliente.post(
        f"{BASE}/requerimientos-detalle",
        json={
            "requerimiento_id": req,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "cantidad": 50,
        },
    )
    assert r.status_code == 201, r.text

    # 2. Nace el pedido
    pedido = (
        await cliente.post(
            f"{BASE}/pedidos",
            json={"requerimiento_id": req, "estado_id": estado},
        )
    ).json()["id"]
    assert (
        await cliente.post(
            f"{BASE}/pedidos-detalle",
            json={
                "pedido_id": pedido,
                "producto_id": producto,
                "unidad_medida_id": unidad,
                "cantidad": 50,
            },
        )
    ).status_code == 201

    # 3. Un proveedor cotiza
    cot = (
        await cliente.post(
            f"{BASE}/cotizaciones",
            json={
                "pedido_id": pedido,
                "proveedor_id": proveedor,
                "estado_id": estado,
                "tiempo_atencion": 3,
            },
        )
    ).json()["id"]
    assert (
        await cliente.post(
            f"{BASE}/cotizaciones-detalle",
            json={
                "cotizacion_id": cot,
                "producto_id": producto,
                "unidad_medida_id": unidad,
                "cantidad": 50,
                "precio_unitario": "2.50",
            },
        )
    ).status_code == 201

    # 4. Se emite la orden de compra
    orden = (
        await cliente.post(
            f"{BASE}/ordenes-compra",
            json={"cotizacion_id": cot, "estado_id": estado},
        )
    ).json()["id"]
    assert (
        await cliente.post(
            f"{BASE}/ordenes-compra-detalle",
            json={
                "orden_compra_id": orden,
                "producto_id": producto,
                "unidad_medida_id": unidad,
                "cantidad": 50,
                "precio_unitario": "2.50",
            },
        )
    ).status_code == 201

    # 5. Llega la guía y con ella el lote
    guia = (
        await cliente.post(
            f"{BASE}/guias-remision",
            json={"orden_compra_id": orden, "estado_id": estado},
        )
    ).json()["id"]
    # La guía declara primero qué trae; el lote se cuadra contra esa línea.
    assert (
        await cliente.post(
            f"{BASE}/guias-remision-detalle",
            json={
                "guia_remision_id": guia,
                "producto_id": producto,
                "unidad_medida_id": unidad,
                "cantidad": 50,
            },
        )
    ).status_code == 201
    r = await cliente.post(
        f"{BASE}/productos-lote",
        json={
            "almacen_id": almacen,
            "guia_remision_id": guia,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "fecha_ingreso": "2026-08-12",
            "cantidad": 50,
            "codigo_lote": "L-0001",
        },
    )
    assert r.status_code == 201, r.text

    # Y desde el lote se vuelve al proveedor por la cadena de ids
    lote = r.json()
    assert lote["producto_id"] == producto
    g = (await cliente.get(f"{BASE}/guias-remision/{lote['guia_remision_id']}")).json()
    o = (await cliente.get(f"{BASE}/ordenes-compra/{g['orden_compra_id']}")).json()
    # La orden ya no guarda el proveedor: se llega por su cotización, que es
    # la única fuente del dato.
    c = (await cliente.get(f"{BASE}/cotizaciones/{o['cotizacion_id']}")).json()
    assert c["proveedor_id"] == proveedor


# ===================== Montos calculados en el servidor =====================


async def test_el_monto_de_la_linea_lo_calcula_el_servidor(cliente, catalogo):
    estado = await _estado(cliente)
    unidad = await _unidad(cliente)
    producto = await _producto(cliente, catalogo)
    proveedor = await _proveedor(cliente)
    almacen = await _almacen(cliente)
    req = (
        await cliente.post(
            f"{BASE}/requerimientos", json={"almacen_id": almacen, "estado_id": estado}
        )
    ).json()["id"]
    pedido = (
        await cliente.post(
            f"{BASE}/pedidos", json={"requerimiento_id": req, "estado_id": estado}
        )
    ).json()["id"]
    cot = (
        await cliente.post(
            f"{BASE}/cotizaciones",
            json={
                "pedido_id": pedido,
                "proveedor_id": proveedor,
                "estado_id": estado,
            },
        )
    ).json()["id"]

    r = await cliente.post(
        f"{BASE}/cotizaciones-detalle",
        json={
            "cotizacion_id": cot,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "cantidad": 10,
            "precio_unitario": "2.50",
        },
    )

    assert Decimal(r.json()["monto_producto"]) == Decimal("25.00")
    cotizacion = (await cliente.get(f"{BASE}/cotizaciones/{cot}")).json()
    assert Decimal(cotizacion["monto_total"]) == Decimal("25.00")


async def test_el_total_suma_las_lineas_y_baja_al_quitar_una(cliente, catalogo):
    estado = await _estado(cliente)
    unidad = await _unidad(cliente)
    uno = await _producto(cliente, catalogo, "SKU-UNO")
    dos = await _producto(cliente, catalogo, "SKU-DOS")
    proveedor = await _proveedor(cliente)
    almacen = await _almacen(cliente)
    req = (
        await cliente.post(
            f"{BASE}/requerimientos", json={"almacen_id": almacen, "estado_id": estado}
        )
    ).json()["id"]
    pedido = (
        await cliente.post(
            f"{BASE}/pedidos", json={"requerimiento_id": req, "estado_id": estado}
        )
    ).json()["id"]
    cot = (
        await cliente.post(
            f"{BASE}/cotizaciones",
            json={
                "pedido_id": pedido,
                "proveedor_id": proveedor,
                "estado_id": estado,
            },
        )
    ).json()["id"]

    base = {"cotizacion_id": cot, "unidad_medida_id": unidad}
    linea_uno = (
        await cliente.post(
            f"{BASE}/cotizaciones-detalle",
            json={
                **base,
                "producto_id": uno,
                "cantidad": 10,
                "precio_unitario": "2.00",
            },
        )
    ).json()["id"]
    await cliente.post(
        f"{BASE}/cotizaciones-detalle",
        json={**base, "producto_id": dos, "cantidad": 5, "precio_unitario": "4.00"},
    )

    total = (await cliente.get(f"{BASE}/cotizaciones/{cot}")).json()["monto_total"]
    assert Decimal(total) == Decimal("40.00")  # 20 + 20

    await cliente.delete(f"{BASE}/cotizaciones-detalle/{linea_uno}")

    total = (await cliente.get(f"{BASE}/cotizaciones/{cot}")).json()["monto_total"]
    assert Decimal(total) == Decimal("20.00"), "dar de baja una línea debe restarla"


async def test_el_cliente_no_puede_imponer_el_monto(cliente, catalogo):
    """`monto_producto` se ignora si llega: lo manda el servidor."""
    estado = await _estado(cliente)
    unidad = await _unidad(cliente)
    producto = await _producto(cliente, catalogo)
    proveedor = await _proveedor(cliente)
    almacen = await _almacen(cliente)
    req = (
        await cliente.post(
            f"{BASE}/requerimientos", json={"almacen_id": almacen, "estado_id": estado}
        )
    ).json()["id"]
    pedido = (
        await cliente.post(
            f"{BASE}/pedidos", json={"requerimiento_id": req, "estado_id": estado}
        )
    ).json()["id"]
    cot = (
        await cliente.post(
            f"{BASE}/cotizaciones",
            json={
                "pedido_id": pedido,
                "proveedor_id": proveedor,
                "estado_id": estado,
            },
        )
    ).json()["id"]

    r = await cliente.post(
        f"{BASE}/cotizaciones-detalle",
        json={
            "cotizacion_id": cot,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "cantidad": 10,
            "precio_unitario": "2.50",
            "monto_producto": "999999.00",
        },
    )

    assert Decimal(r.json()["monto_producto"]) == Decimal("25.00")


# ===================== Integridad =====================


async def test_el_producto_no_se_repite_en_la_misma_linea(cliente, catalogo):
    estado = await _estado(cliente)
    almacen = await _almacen(cliente)
    unidad = await _unidad(cliente)
    producto = await _producto(cliente, catalogo)
    req = (
        await cliente.post(
            f"{BASE}/requerimientos", json={"almacen_id": almacen, "estado_id": estado}
        )
    ).json()["id"]
    linea = {
        "requerimiento_id": req,
        "producto_id": producto,
        "unidad_medida_id": unidad,
        "cantidad": 5,
    }

    assert (
        await cliente.post(f"{BASE}/requerimientos-detalle", json=linea)
    ).status_code == 201

    r = await cliente.post(f"{BASE}/requerimientos-detalle", json=linea)

    assert r.status_code == 409


@pytest.mark.parametrize("cantidad", [0, -1])
async def test_cantidad_no_positiva_es_422(cliente, catalogo, cantidad):
    """Antes `Field(min=1)` no validaba nada y un 0 pasaba."""
    estado = await _estado(cliente)
    almacen = await _almacen(cliente)
    unidad = await _unidad(cliente)
    producto = await _producto(cliente, catalogo)
    req = (
        await cliente.post(
            f"{BASE}/requerimientos", json={"almacen_id": almacen, "estado_id": estado}
        )
    ).json()["id"]

    r = await cliente.post(
        f"{BASE}/requerimientos-detalle",
        json={
            "requerimiento_id": req,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "cantidad": cantidad,
        },
    )

    assert r.status_code == 422


async def test_filtrar_lineas_por_requerimiento(cliente, catalogo):
    estado = await _estado(cliente)
    almacen = await _almacen(cliente)
    unidad = await _unidad(cliente)
    producto = await _producto(cliente, catalogo)
    req_a = (
        await cliente.post(
            f"{BASE}/requerimientos", json={"almacen_id": almacen, "estado_id": estado}
        )
    ).json()["id"]
    req_b = (
        await cliente.post(
            f"{BASE}/requerimientos", json={"almacen_id": almacen, "estado_id": estado}
        )
    ).json()["id"]
    linea_a = (
        await cliente.post(
            f"{BASE}/requerimientos-detalle",
            json={
                "requerimiento_id": req_a,
                "producto_id": producto,
                "unidad_medida_id": unidad,
                "cantidad": 1,
            },
        )
    ).json()["id"]
    await cliente.post(
        f"{BASE}/requerimientos-detalle",
        json={
            "requerimiento_id": req_b,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "cantidad": 2,
        },
    )

    r = await cliente.get(
        f"{BASE}/requerimientos-detalle", params={"requerimiento_id": req_a}
    )

    assert [x["id"] for x in r.json()["items"]] == [linea_a]


# ===================== Total de la orden de compra =====================


async def _orden(cliente, catalogo) -> tuple[str, str, str]:
    """Orden de compra lista para recibir líneas. Devuelve (orden, unidad, producto)."""
    estado = await _estado(cliente)
    unidad = await _unidad(cliente)
    producto = await _producto(cliente, catalogo)
    proveedor = await _proveedor(cliente)
    almacen = await _almacen(cliente)
    req = (
        await cliente.post(
            f"{BASE}/requerimientos", json={"almacen_id": almacen, "estado_id": estado}
        )
    ).json()["id"]
    pedido = (
        await cliente.post(
            f"{BASE}/pedidos", json={"requerimiento_id": req, "estado_id": estado}
        )
    ).json()["id"]
    cot = (
        await cliente.post(
            f"{BASE}/cotizaciones",
            json={
                "pedido_id": pedido,
                "proveedor_id": proveedor,
                "estado_id": estado,
            },
        )
    ).json()["id"]
    r = await cliente.post(
        f"{BASE}/ordenes-compra", json={"cotizacion_id": cot, "estado_id": estado}
    )
    assert r.status_code == 201, r.text
    return r.json()["id"], unidad, producto


async def test_la_orden_nace_con_total_en_cero(cliente, catalogo):
    """Se crea antes que sus líneas, así que no puede exigir un total."""
    orden, _, _ = await _orden(cliente, catalogo)

    r = await cliente.get(f"{BASE}/ordenes-compra/{orden}")

    assert Decimal(r.json()["monto_total"]) == Decimal("0.00")


async def test_el_total_de_la_orden_lo_suman_sus_lineas(cliente, catalogo):
    orden, unidad, producto = await _orden(cliente, catalogo)

    await cliente.post(
        f"{BASE}/ordenes-compra-detalle",
        json={
            "orden_compra_id": orden,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "cantidad": 50,
            "precio_unitario": "2.50",
        },
    )

    r = await cliente.get(f"{BASE}/ordenes-compra/{orden}")
    assert Decimal(r.json()["monto_total"]) == Decimal("125.00")


async def test_el_cliente_no_puede_imponer_el_total_de_la_orden(cliente, catalogo):
    """`monto_total` no está en el Create: si llega, se ignora."""
    estado = await _estado(cliente)
    proveedor = await _proveedor(cliente)
    almacen = await _almacen(cliente)
    req = (
        await cliente.post(
            f"{BASE}/requerimientos", json={"almacen_id": almacen, "estado_id": estado}
        )
    ).json()["id"]
    pedido = (
        await cliente.post(
            f"{BASE}/pedidos", json={"requerimiento_id": req, "estado_id": estado}
        )
    ).json()["id"]
    cot = (
        await cliente.post(
            f"{BASE}/cotizaciones",
            json={"pedido_id": pedido, "proveedor_id": proveedor, "estado_id": estado},
        )
    ).json()["id"]

    r = await cliente.post(
        f"{BASE}/ordenes-compra",
        json={
            "cotizacion_id": cot,
            "estado_id": estado,
            "monto_total": "999999.00",
        },
    )

    assert Decimal(r.json()["monto_total"]) == Decimal("0.00")


async def test_dar_de_baja_una_linea_baja_el_total_de_la_orden(cliente, catalogo):
    orden, unidad, producto = await _orden(cliente, catalogo)
    linea = (
        await cliente.post(
            f"{BASE}/ordenes-compra-detalle",
            json={
                "orden_compra_id": orden,
                "producto_id": producto,
                "unidad_medida_id": unidad,
                "cantidad": 10,
                "precio_unitario": "3.00",
            },
        )
    ).json()["id"]

    await cliente.delete(f"{BASE}/ordenes-compra-detalle/{linea}")

    r = await cliente.get(f"{BASE}/ordenes-compra/{orden}")
    assert Decimal(r.json()["monto_total"]) == Decimal("0.00")


# ===================== Detalle de la guía de remisión =====================


async def _guia(cliente, catalogo) -> tuple[str, str, str]:
    """Guía lista para recibir líneas. Devuelve (guia, unidad, producto)."""
    orden, unidad, producto = await _orden(cliente, catalogo)
    estado = await _estado(cliente)
    r = await cliente.post(
        f"{BASE}/guias-remision",
        json={"orden_compra_id": orden, "estado_id": estado},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"], unidad, producto


async def test_crear_linea_de_guia(cliente, catalogo):
    guia, unidad, producto = await _guia(cliente, catalogo)

    r = await cliente.post(
        f"{BASE}/guias-remision-detalle",
        json={
            "guia_remision_id": guia,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "cantidad": 48,
        },
    )

    assert r.status_code == 201, r.text
    assert r.json()["cantidad"] == 48


async def test_cantidad_cero_es_valida_en_la_guia(cliente, catalogo):
    """Sirve para dejar constancia de lo que el proveedor no entregó."""
    guia, unidad, producto = await _guia(cliente, catalogo)

    r = await cliente.post(
        f"{BASE}/guias-remision-detalle",
        json={
            "guia_remision_id": guia,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "cantidad": 0,
        },
    )

    assert r.status_code == 201, r.text


async def test_cantidad_negativa_en_la_guia_es_422(cliente, catalogo):
    """Antes `Field(min=0)` no validaba y un -5 entraba."""
    guia, unidad, producto = await _guia(cliente, catalogo)

    r = await cliente.post(
        f"{BASE}/guias-remision-detalle",
        json={
            "guia_remision_id": guia,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "cantidad": -5,
        },
    )

    assert r.status_code == 422


async def test_el_producto_no_se_repite_en_la_misma_guia(cliente, catalogo):
    guia, unidad, producto = await _guia(cliente, catalogo)
    linea = {
        "guia_remision_id": guia,
        "producto_id": producto,
        "unidad_medida_id": unidad,
        "cantidad": 10,
    }

    assert (
        await cliente.post(f"{BASE}/guias-remision-detalle", json=linea)
    ).status_code == 201

    r = await cliente.post(f"{BASE}/guias-remision-detalle", json=linea)

    assert r.status_code == 409


async def test_filtrar_lineas_por_guia(cliente, catalogo):
    guia, unidad, producto = await _guia(cliente, catalogo)
    linea = (
        await cliente.post(
            f"{BASE}/guias-remision-detalle",
            json={
                "guia_remision_id": guia,
                "producto_id": producto,
                "unidad_medida_id": unidad,
                "cantidad": 7,
            },
        )
    ).json()["id"]

    r = await cliente.get(
        f"{BASE}/guias-remision-detalle", params={"guia_remision_id": guia}
    )

    assert [x["id"] for x in r.json()["items"]] == [linea]


# ===================== Lotes cuadrados contra la guía =====================


async def test_los_lotes_no_pueden_superar_lo_declarado_en_la_guia(cliente, catalogo):
    guia, unidad, producto = await _guia(cliente, catalogo)
    almacen = await _almacen_de_la_cadena(cliente)
    await cliente.post(
        f"{BASE}/guias-remision-detalle",
        json={
            "guia_remision_id": guia,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "cantidad": 48,
        },
    )
    lote = {
        "almacen_id": almacen,
        "guia_remision_id": guia,
        "producto_id": producto,
        "fecha_ingreso": "2026-08-12",
    }

    # Una línea de 48 se puede partir en varios lotes...
    assert (
        await cliente.post(
            f"{BASE}/productos-lote",
            json={**lote, "cantidad": 30, "codigo_lote": "L-1"},
        )
    ).status_code == 201
    assert (
        await cliente.post(
            f"{BASE}/productos-lote",
            json={**lote, "cantidad": 18, "codigo_lote": "L-2"},
        )
    ).status_code == 201

    # ...pero la suma no puede pasarse.
    r = await cliente.post(
        f"{BASE}/productos-lote", json={**lote, "cantidad": 1, "codigo_lote": "L-3"}
    )

    assert r.status_code == 409
    assert "49" in r.json()["detail"] and "48" in r.json()["detail"]


async def test_un_lote_de_algo_que_la_guia_no_declara_es_400(cliente, catalogo):
    guia, _, producto = await _guia(cliente, catalogo)
    almacen = await _almacen_de_la_cadena(cliente)

    r = await cliente.post(
        f"{BASE}/productos-lote",
        json={
            "almacen_id": almacen,
            "guia_remision_id": guia,
            "producto_id": producto,
            "fecha_ingreso": "2026-08-12",
            "cantidad": 5,
            "codigo_lote": "L-9",
        },
    )

    assert r.status_code == 400
    assert "no declara" in r.json()["detail"]


async def test_editar_un_lote_tambien_se_valida(cliente, catalogo):
    guia, unidad, producto = await _guia(cliente, catalogo)
    almacen = await _almacen_de_la_cadena(cliente)
    await cliente.post(
        f"{BASE}/guias-remision-detalle",
        json={
            "guia_remision_id": guia,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "cantidad": 10,
        },
    )
    lote = (
        await cliente.post(
            f"{BASE}/productos-lote",
            json={
                "almacen_id": almacen,
                "guia_remision_id": guia,
                "producto_id": producto,
                "fecha_ingreso": "2026-08-12",
                "cantidad": 10,
                "codigo_lote": "L-1",
            },
        )
    ).json()["id"]

    # Subirlo por encima de lo declarado no vale...
    assert (
        await cliente.patch(f"{BASE}/productos-lote/{lote}", json={"cantidad": 11})
    ).status_code == 409
    # ...pero bajarlo sí, y el propio lote no se cuenta dos veces.
    assert (
        await cliente.patch(f"{BASE}/productos-lote/{lote}", json={"cantidad": 4})
    ).status_code == 200


async def test_no_se_puede_rebajar_la_guia_por_debajo_de_sus_lotes(cliente, catalogo):
    """Si no, bastaría con editar la guía para esquivar la regla del lote."""
    guia, unidad, producto = await _guia(cliente, catalogo)
    almacen = await _almacen_de_la_cadena(cliente)
    linea = (
        await cliente.post(
            f"{BASE}/guias-remision-detalle",
            json={
                "guia_remision_id": guia,
                "producto_id": producto,
                "unidad_medida_id": unidad,
                "cantidad": 20,
            },
        )
    ).json()["id"]
    await cliente.post(
        f"{BASE}/productos-lote",
        json={
            "almacen_id": almacen,
            "guia_remision_id": guia,
            "producto_id": producto,
            "fecha_ingreso": "2026-08-12",
            "cantidad": 15,
            "codigo_lote": "L-1",
        },
    )

    assert (
        await cliente.patch(
            f"{BASE}/guias-remision-detalle/{linea}", json={"cantidad": 10}
        )
    ).status_code == 409
    # Bajar hasta lo ya recibido sí se puede.
    assert (
        await cliente.patch(
            f"{BASE}/guias-remision-detalle/{linea}", json={"cantidad": 15}
        )
    ).status_code == 200


async def test_dar_de_baja_la_linea_con_lotes_es_409(cliente, catalogo):
    guia, unidad, producto = await _guia(cliente, catalogo)
    almacen = await _almacen_de_la_cadena(cliente)
    linea = (
        await cliente.post(
            f"{BASE}/guias-remision-detalle",
            json={
                "guia_remision_id": guia,
                "producto_id": producto,
                "unidad_medida_id": unidad,
                "cantidad": 5,
            },
        )
    ).json()["id"]
    await cliente.post(
        f"{BASE}/productos-lote",
        json={
            "almacen_id": almacen,
            "guia_remision_id": guia,
            "producto_id": producto,
            "fecha_ingreso": "2026-08-12",
            "cantidad": 5,
            "codigo_lote": "L-1",
        },
    )

    r = await cliente.delete(f"{BASE}/guias-remision-detalle/{linea}")

    assert r.status_code == 409


async def test_dar_de_baja_un_lote_libera_su_cantidad(cliente, catalogo):
    guia, unidad, producto = await _guia(cliente, catalogo)
    almacen = await _almacen_de_la_cadena(cliente)
    await cliente.post(
        f"{BASE}/guias-remision-detalle",
        json={
            "guia_remision_id": guia,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "cantidad": 10,
        },
    )
    lote = {
        "almacen_id": almacen,
        "guia_remision_id": guia,
        "producto_id": producto,
        "fecha_ingreso": "2026-08-12",
    }
    primero = (
        await cliente.post(
            f"{BASE}/productos-lote",
            json={**lote, "cantidad": 10, "codigo_lote": "L-1"},
        )
    ).json()["id"]

    # Con el primero activo no cabe nada más...
    assert (
        await cliente.post(
            f"{BASE}/productos-lote", json={**lote, "cantidad": 1, "codigo_lote": "L-2"}
        )
    ).status_code == 409

    await cliente.delete(f"{BASE}/productos-lote/{primero}")

    # ...y al darlo de baja, su cantidad deja de contar.
    assert (
        await cliente.post(
            f"{BASE}/productos-lote",
            json={**lote, "cantidad": 10, "codigo_lote": "L-3"},
        )
    ).status_code == 201


# ============ Guía en paquetes, almacén en unidad mínima ============


async def _guia_con_unidades(cliente, catalogo):
    """Guía lista, con dos unidades: caja de 12 y unidad suelta."""
    orden, _, producto = await _orden(cliente, catalogo)
    estado = await _estado(cliente)
    guia = (
        await cliente.post(
            f"{BASE}/guias-remision",
            json={"orden_compra_id": orden, "estado_id": estado},
        )
    ).json()["id"]
    caja = await _unidad(cliente, "Caja x12", "CAJA12", factor=12)
    return guia, producto, caja


async def test_cuatro_cajas_de_doce_equivalen_a_48_unidades(cliente, catalogo):
    """El caso real: la guía viene por paquetes y el almacén en unidad mínima."""
    guia, producto, caja = await _guia_con_unidades(cliente, catalogo)
    almacen = await _almacen_de_la_cadena(cliente)

    # La guía declara 4 cajas = 48 unidades mínimas
    await cliente.post(
        f"{BASE}/guias-remision-detalle",
        json={
            "guia_remision_id": guia,
            "producto_id": producto,
            "unidad_medida_id": caja,
            "cantidad": 4,
        },
    )

    lote = {
        "almacen_id": almacen,
        "guia_remision_id": guia,
        "producto_id": producto,
        "fecha_ingreso": "2026-08-12",
    }
    # 48 unidades sueltas caben justo
    r = await cliente.post(
        f"{BASE}/productos-lote", json={**lote, "cantidad": 48, "codigo_lote": "L-1"}
    )
    assert r.status_code == 201, r.text

    # La 49 ya no
    r = await cliente.post(
        f"{BASE}/productos-lote", json={**lote, "cantidad": 1, "codigo_lote": "L-2"}
    )
    assert r.status_code == 409
    assert "49" in r.json()["detail"] and "48" in r.json()["detail"]


async def test_sin_conversion_cuatro_cajas_habrian_admitido_solo_cuatro(
    cliente, catalogo
):
    """Comparar en crudo daba por buena una guía de 4 cajas contra 4 unidades."""
    guia, producto, caja = await _guia_con_unidades(cliente, catalogo)
    almacen = await _almacen_de_la_cadena(cliente)
    await cliente.post(
        f"{BASE}/guias-remision-detalle",
        json={
            "guia_remision_id": guia,
            "producto_id": producto,
            "unidad_medida_id": caja,
            "cantidad": 4,
        },
    )

    r = await cliente.post(
        f"{BASE}/productos-lote",
        json={
            "almacen_id": almacen,
            "guia_remision_id": guia,
            "producto_id": producto,
            "fecha_ingreso": "2026-08-12",
            "cantidad": 20,
            "codigo_lote": "L-1",
        },
    )

    assert r.status_code == 201, "20 unidades caben en 4 cajas de 12"


async def test_varios_lotes_se_suman_y_se_comparan_convertidos(cliente, catalogo):
    """El lote ya no trae unidad propia: todos van en la de venta del producto
    y lo que se compara es su suma contra la guía convertida."""
    guia, producto, caja = await _guia_con_unidades(cliente, catalogo)
    almacen = await _almacen_de_la_cadena(cliente)
    await cliente.post(
        f"{BASE}/guias-remision-detalle",
        json={
            "guia_remision_id": guia,
            "producto_id": producto,
            "unidad_medida_id": caja,
            "cantidad": 4,  # 48 unidades mínimas
        },
    )
    base = {
        "almacen_id": almacen,
        "guia_remision_id": guia,
        "producto_id": producto,
        "fecha_ingreso": "2026-08-12",
    }

    # 36 + 12 = 48 justo
    assert (
        await cliente.post(
            f"{BASE}/productos-lote",
            json={**base, "cantidad": 36, "codigo_lote": "L-1"},
        )
    ).status_code == 201
    assert (
        await cliente.post(
            f"{BASE}/productos-lote",
            json={**base, "cantidad": 12, "codigo_lote": "L-2"},
        )
    ).status_code == 201

    # Una más se pasa
    r = await cliente.post(
        f"{BASE}/productos-lote",
        json={**base, "cantidad": 1, "codigo_lote": "L-3"},
    )
    assert r.status_code == 409


async def test_sin_equivalencia_registrada_es_400(cliente, catalogo):
    """La unidad que le falta el factor es la de venta del producto: sin ella
    no hay con qué llevar el lote a unidad mínima."""
    guia, producto, caja = await _guia_con_unidades(cliente, catalogo)
    almacen = await _almacen_de_la_cadena(cliente)
    await cliente.post(
        f"{BASE}/guias-remision-detalle",
        json={
            "guia_remision_id": guia,
            "producto_id": producto,
            "unidad_medida_id": caja,
            "cantidad": 4,
        },
    )
    # El alta ya no deja crear una unidad sin equivalencia, así que para llegar
    # a este estado hay que darla de baja después. Sigue siendo alcanzable —los
    # registros anteriores a que el alta exigiera el factor están así— y es lo
    # que este 400 protege.
    equivalencia = (
        await cliente.get(
            f"{BASE}/tablas-equivalencia",
            params={"unidad_medida_id": catalogo["unidad_venta"]},
        )
    ).json()["items"][0]["id"]
    await cliente.delete(f"{BASE}/tablas-equivalencia/{equivalencia}")

    r = await cliente.post(
        f"{BASE}/productos-lote",
        json={
            "almacen_id": almacen,
            "guia_remision_id": guia,
            "producto_id": producto,
            "fecha_ingreso": "2026-08-12",
            "cantidad": 1,
            "codigo_lote": "L-X",
        },
    )

    assert r.status_code == 400
    assert "UBASE" in r.json()["detail"]


async def test_una_unidad_no_puede_tener_dos_factores(cliente):
    """El `UNIQUE` sigue siendo la última defensa.

    Con el factor viajando en el alta de la unidad es más difícil llegar acá,
    pero `/tablas-equivalencia` sigue abierto y una segunda fila volvería la
    conversión no determinista.
    """
    unidad = await _unidad(cliente, "Caja", "CJ", factor=12)

    r = await cliente.post(
        f"{BASE}/tablas-equivalencia",
        json={"unidad_medida_id": unidad, "factor_conversion": 24},
    )

    assert r.status_code == 409, "la conversión dejaría de ser determinista"
