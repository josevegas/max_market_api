"""La venta descuenta el stock del que sale.

Emitir el comprobante y sacar la mercadería son el mismo hecho. El módulo
estaba esbozado sin nada de esto —y sin ser siquiera un modelo de SQLAlchemy—,
así que acá se prueba lo que hace que la venta signifique algo: que el stock
baje, que baje del lote correcto, y que anular lo devuelva a donde estaba.

La salida es FEFO: vence primero, sale primero.
"""

from __future__ import annotations

from app.modules.movimientos.constantes import CODIGO_PENDIENTE
from tests.test_cadena_compras import BASE, _almacen, _estado
from tests.test_recepcion_detalle import _guia_con_linea
from tests.test_stock import _lotes, _recibir


async def _tipo(cliente, descripcion="Boleta", codigo="03") -> str:
    r = await cliente.post(
        f"{BASE}/tipos-comprobante",
        json={"descripcion": descripcion, "codigo": codigo},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _venta(cliente, almacen, tipo=None, numero="00000001", **extra) -> str:
    r = await cliente.post(
        f"{BASE}/ventas",
        json={
            "almacen_id": almacen,
            "tipo_comprobante_id": tipo or await _tipo(cliente),
            "serie_comprobante": "B001",
            "numero_comprobante": numero,
            **extra,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _vender(cliente, venta, producto, cantidad):
    return await cliente.post(
        f"{BASE}/ventas-detalle",
        json={"venta_id": venta, "producto_id": producto, "cantidad": cantidad},
    )


async def _con_stock(cliente, catalogo, cantidad=50, **lote):
    """Un producto con stock recibido y su ficha en el almacén.

    Devuelve (almacen, producto, unidad).
    """
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, cantidad)
    almacen = await _almacen(cliente)
    # La ficha con el precio la crea la recepción: registrar un lote es decir
    # que ese producto vive en ese almacén.
    await _recibir(cliente, recepcion, producto, unidad, cantidad, **lote)
    return almacen, producto, unidad


# ===================== El comprobante =====================


async def test_emitir_una_venta(cliente, catalogo):
    """El módulo no era un modelo: no había forma de registrar una venta."""
    almacen, _, _ = await _con_stock(cliente, catalogo, codigo_lote="L-1")

    r = await cliente.post(
        f"{BASE}/ventas",
        json={
            "almacen_id": almacen,
            "tipo_comprobante_id": await _tipo(cliente),
            "serie_comprobante": "B001",
            "numero_comprobante": "00000001",
        },
    )

    assert r.status_code == 201, r.text
    assert r.json()["monto_total"] == "0.00"


async def test_la_venta_nace_pendiente(cliente, catalogo):
    almacen, _, _ = await _con_stock(cliente, catalogo, codigo_lote="L-1")

    venta = await _venta(cliente, almacen)

    r = await cliente.get(f"{BASE}/ventas/{venta}")
    assert r.json()["estado_id"] == await _estado(cliente, CODIGO_PENDIENTE)


async def test_el_mismo_comprobante_dos_veces_es_409(cliente, catalogo):
    almacen, _, _ = await _con_stock(cliente, catalogo, codigo_lote="L-1")
    tipo = await _tipo(cliente)
    await _venta(cliente, almacen, tipo)

    r = await cliente.post(
        f"{BASE}/ventas",
        json={
            "almacen_id": almacen,
            "tipo_comprobante_id": tipo,
            "serie_comprobante": "B001",
            "numero_comprobante": "00000001",
        },
    )

    assert r.status_code == 409


async def test_la_factura_exige_ruc(cliente, catalogo):
    """La boleta se emite sin identificar al cliente; la factura, no."""
    almacen, _, _ = await _con_stock(cliente, catalogo, codigo_lote="L-1")

    r = await cliente.post(
        f"{BASE}/ventas",
        json={
            "almacen_id": almacen,
            "tipo_comprobante_id": await _tipo(cliente, "Factura", "01"),
            "serie_comprobante": "F001",
            "numero_comprobante": "00000001",
        },
    )

    assert r.status_code == 409
    assert "RUC" in r.json()["detail"]


async def test_la_boleta_no_lo_exige(cliente, catalogo):
    almacen, _, _ = await _con_stock(cliente, catalogo, codigo_lote="L-1")

    r = await cliente.post(
        f"{BASE}/ventas",
        json={
            "almacen_id": almacen,
            "tipo_comprobante_id": await _tipo(cliente, "Boleta", "03"),
            "serie_comprobante": "B001",
            "numero_comprobante": "00000001",
        },
    )

    assert r.status_code == 201, r.text


# ===================== Vender descuenta el stock =====================


async def test_vender_baja_el_stock(cliente, catalogo):
    """El caso que da sentido a todo esto: se vende y hay menos."""
    almacen, producto, _ = await _con_stock(cliente, catalogo, 50, codigo_lote="L-1")
    venta = await _venta(cliente, almacen)

    r = await _vender(cliente, venta, producto, 20)

    assert r.status_code == 201, r.text
    assert (await _lotes(cliente, producto))[0]["cantidad"] == 30


async def test_el_precio_sale_de_la_ficha_del_almacen(cliente, catalogo):
    """La caja no lo envía: si pudiera, se podría vender por debajo del costo
    de la partida que está en el almacén sin que nada avisara."""
    almacen, producto, _ = await _con_stock(cliente, catalogo, 50, codigo_lote="L-1")
    venta = await _venta(cliente, almacen)

    r = await _vender(cliente, venta, producto, 3)

    ficha = (
        await cliente.get(f"{BASE}/productos-almacen", params={"producto_id": producto})
    ).json()["items"][0]
    assert r.json()["precio_unitario"] == ficha["precio_venta_tienda"]


async def test_el_total_de_la_venta_lo_suman_sus_lineas(cliente, catalogo):
    almacen, producto, _ = await _con_stock(cliente, catalogo, 50, codigo_lote="L-1")
    venta = await _venta(cliente, almacen)

    linea = (await _vender(cliente, venta, producto, 4)).json()

    r = await cliente.get(f"{BASE}/ventas/{venta}")
    assert r.json()["monto_total"] == linea["monto"]


async def test_vender_mas_de_lo_que_hay_es_409(cliente, catalogo):
    """Sin stock no se emite la línea: el comprobante quedaría respaldando
    mercadería que no salió."""
    almacen, producto, _ = await _con_stock(cliente, catalogo, 10, codigo_lote="L-1")
    venta = await _venta(cliente, almacen)

    r = await _vender(cliente, venta, producto, 11)

    assert r.status_code == 409
    assert "11" in r.json()["detail"] and "10" in r.json()["detail"]
    assert (await _lotes(cliente, producto))[0]["cantidad"] == 10, "no se tocó nada"


async def test_un_producto_que_nunca_entro_no_se_puede_vender(cliente, catalogo):
    """La ficha la crea la recepción, así que un producto que nunca llegó a
    este almacén no tiene precio. Uno inventado sería peor que un 400."""
    from tests.conftest import producto_valido

    almacen, _, _ = await _con_stock(cliente, catalogo, codigo_lote="L-1")
    nunca_llego = (
        await cliente.post(f"{BASE}/productos", json=producto_valido(catalogo, "NUN-1"))
    ).json()["id"]
    venta = await _venta(cliente, almacen)

    r = await _vender(cliente, venta, nunca_llego, 1)

    assert r.status_code == 400
    assert "ficha" in r.json()["detail"]


# ===================== Vence primero, sale primero =====================


async def _dos_lotes(cliente, catalogo):
    """Dos lotes del mismo producto: uno que vence antes y otro después.

    Devuelve (almacen, producto, unidad).
    """
    from tests.test_stock import _recepcion_en

    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    almacen = await _almacen(cliente)
    await cliente.post(
        f"{BASE}/recepciones-detalle",
        json={
            "recepcion_id": recepcion,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "cantidad_esperada": 12,
            "cantidad_ingresada": 12,
            "codigo_lote": "VENCE-ANTES",
        },
    )
    otra = await _recepcion_en(cliente, almacen, producto, unidad)
    await cliente.post(
        f"{BASE}/recepciones-detalle",
        json={
            "recepcion_id": otra,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "cantidad_esperada": 40,
            "cantidad_ingresada": 40,
            "codigo_lote": "VENCE-DESPUES",
        },
    )
    por_codigo = {x["codigo_lote"]: x["id"] for x in await _lotes(cliente, producto)}
    await cliente.patch(
        f"{BASE}/productos-lote/{por_codigo['VENCE-ANTES']}",
        json={"fecha_vencimiento": "2026-08-20"},
    )
    await cliente.patch(
        f"{BASE}/productos-lote/{por_codigo['VENCE-DESPUES']}",
        json={"fecha_vencimiento": "2026-09-05"},
    )
    return almacen, producto, unidad


async def _por_codigo(cliente, producto) -> dict:
    return {x["codigo_lote"]: x["cantidad"] for x in await _lotes(cliente, producto)}


async def test_sale_primero_el_que_vence_antes(cliente, catalogo):
    """Sacar por antigüedad de ingreso dejaría vencer lo que caduca antes."""
    almacen, producto, _ = await _dos_lotes(cliente, catalogo)
    venta = await _venta(cliente, almacen)

    assert (await _vender(cliente, venta, producto, 10)).status_code == 201

    assert await _por_codigo(cliente, producto) == {
        "VENCE-ANTES": 2,
        "VENCE-DESPUES": 40,
    }


async def test_cuando_no_alcanza_sigue_por_el_siguiente(cliente, catalogo):
    almacen, producto, _ = await _dos_lotes(cliente, catalogo)
    venta = await _venta(cliente, almacen)

    assert (await _vender(cliente, venta, producto, 30)).status_code == 201

    assert await _por_codigo(cliente, producto) == {
        "VENCE-ANTES": 0,
        "VENCE-DESPUES": 22,
    }


# ===================== Anular devuelve la mercadería =====================


async def test_anular_la_linea_devuelve_el_stock(cliente, catalogo):
    almacen, producto, _ = await _con_stock(cliente, catalogo, 50, codigo_lote="L-1")
    venta = await _venta(cliente, almacen)
    linea = (await _vender(cliente, venta, producto, 20)).json()["id"]

    r = await cliente.delete(f"{BASE}/ventas-detalle/{linea}")

    assert r.status_code == 200, r.text
    assert (await _lotes(cliente, producto))[0]["cantidad"] == 50


async def test_devuelve_a_los_lotes_de_los_que_salio(cliente, catalogo):
    """Devolver por FEFO pondría la mercadería en un lote con otro
    vencimiento: el total cuadraría mientras el detalle miente."""
    almacen, producto, _ = await _dos_lotes(cliente, catalogo)
    venta = await _venta(cliente, almacen)
    linea = (await _vender(cliente, venta, producto, 30)).json()["id"]

    await cliente.delete(f"{BASE}/ventas-detalle/{linea}")

    assert await _por_codigo(cliente, producto) == {
        "VENCE-ANTES": 12,
        "VENCE-DESPUES": 40,
    }


async def test_anular_la_linea_baja_el_total(cliente, catalogo):
    almacen, producto, _ = await _con_stock(cliente, catalogo, 50, codigo_lote="L-1")
    venta = await _venta(cliente, almacen)
    linea = (await _vender(cliente, venta, producto, 20)).json()["id"]

    await cliente.delete(f"{BASE}/ventas-detalle/{linea}")

    r = await cliente.get(f"{BASE}/ventas/{venta}")
    assert r.json()["monto_total"] == "0.00"


async def test_corregir_la_cantidad_no_duplica_el_descuento(cliente, catalogo):
    """Se devuelve todo y se vuelve a sacar: el almacén queda como si la línea
    se hubiera cargado bien la primera vez."""
    almacen, producto, _ = await _con_stock(cliente, catalogo, 50, codigo_lote="L-1")
    venta = await _venta(cliente, almacen)
    linea = (await _vender(cliente, venta, producto, 30)).json()["id"]

    r = await cliente.patch(f"{BASE}/ventas-detalle/{linea}", json={"cantidad": 10})

    assert r.status_code == 200, r.text
    assert (await _lotes(cliente, producto))[0]["cantidad"] == 40


async def test_corregir_hacia_arriba_tambien_cuadra(cliente, catalogo):
    almacen, producto, _ = await _con_stock(cliente, catalogo, 50, codigo_lote="L-1")
    venta = await _venta(cliente, almacen)
    linea = (await _vender(cliente, venta, producto, 10)).json()["id"]

    r = await cliente.patch(f"{BASE}/ventas-detalle/{linea}", json={"cantidad": 45})

    assert r.status_code == 200, r.text
    assert (await _lotes(cliente, producto))[0]["cantidad"] == 5


# ===================== El stock que se ve refleja la venta =====================


async def test_la_consulta_de_stock_baja_al_vender(cliente, catalogo):
    """Es la vuelta completa: entra por recepción, sale por venta, y lo que el
    almacén dice tener lo refleja."""
    almacen, producto, _ = await _con_stock(cliente, catalogo, 50, codigo_lote="L-1")
    venta = await _venta(cliente, almacen)
    await _vender(cliente, venta, producto, 45)

    fila = next(
        x
        for x in (await cliente.get(f"{BASE}/almacenes/{almacen}/stock")).json()
        if x["producto_id"] == producto
    )

    assert fila["disponible"] == 5
    assert fila["bajo_minimo"] is False
