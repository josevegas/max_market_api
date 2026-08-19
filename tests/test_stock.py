"""Recibir mercadería es lo que crea stock.

Antes eran dos actos sueltos: la recepción registraba lo que llegó y los lotes
se cargaban a mano contra la guía, sin que nada obligara a que dijeran lo
mismo. Acá se prueba que la línea de recepción alimenta el lote de su almacén y
que lo disponible sale de ahí.

Los helpers de la cadena se reutilizan de `test_recepcion_detalle`: montar una
guía con su recepción abierta es exactamente lo mismo, y duplicarlo sería tener
dos versiones de la cadena que se pueden desincronizar.
"""

from __future__ import annotations

from tests.test_cadena_compras import BASE, _almacen, _aprobar, _proveedor
from tests.test_recepcion_detalle import _guia_con_linea, _unidad


async def _recibir(cliente, recepcion, producto, unidad, ingresada, **extra) -> str:
    r = await cliente.post(
        f"{BASE}/recepciones-detalle",
        json={
            "recepcion_id": recepcion,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "cantidad_esperada": ingresada,
            "cantidad_ingresada": ingresada,
            **extra,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _lotes(cliente, producto) -> list[dict]:
    r = await cliente.get(f"{BASE}/productos-lote", params={"producto_id": producto})
    assert r.status_code == 200, r.text
    return r.json()["items"]


async def _stock(cliente, **params) -> list[dict]:
    almacen = await _almacen(cliente)
    r = await cliente.get(f"{BASE}/almacenes/{almacen}/stock", params=params)
    assert r.status_code == 200, r.text
    return r.json()


# ===================== Recibir crea el stock =====================


async def test_recibir_crea_el_lote_con_lo_ingresado(cliente, catalogo):
    """El caso que da sentido a todo esto: se recibe y hay stock."""
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)

    await _recibir(cliente, recepcion, producto, unidad, 30, codigo_lote="L-1")

    lotes = await _lotes(cliente, producto)
    assert len(lotes) == 1
    assert lotes[0]["cantidad"] == 30
    assert lotes[0]["codigo_lote"] == "L-1"


async def test_el_lote_queda_en_el_almacen_de_la_recepcion(cliente, catalogo):
    """Sin almacén el stock no se puede comparar contra el mínimo de la ficha."""
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)

    await _recibir(cliente, recepcion, producto, unidad, 10, codigo_lote="L-1")

    assert (await _lotes(cliente, producto))[0]["almacen_id"] == await _almacen(cliente)


async def test_sin_codigo_de_lote_igual_entra_al_stock(cliente, catalogo):
    """No toda mercadería viene loteada, y esa también es stock."""
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)

    await _recibir(cliente, recepcion, producto, unidad, 12)

    lotes = await _lotes(cliente, producto)
    assert len(lotes) == 1
    assert lotes[0]["cantidad"] == 12
    assert lotes[0]["codigo_lote"].startswith("REC-")


async def test_lo_devuelto_no_descuenta_lo_aceptado(cliente, catalogo):
    """Al almacén entra lo aceptado, tal cual.

    La guía declaraba 40, se aceptaron 25 y los otros 15 se devolvieron o no
    llegaron. `cantidad_ingresada` **ya es** lo aceptado, así que restarle lo
    devuelto dejaría el lote en 10 y el estante tendría 25.
    """
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)

    r = await cliente.post(
        f"{BASE}/recepciones-detalle",
        json={
            "recepcion_id": recepcion,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "cantidad_esperada": 40,
            "cantidad_ingresada": 25,
            "cantidad_devuelta": 15,
            "codigo_lote": "L-1",
        },
    )
    assert r.status_code == 201, r.text

    assert (await _lotes(cliente, producto))[0]["cantidad"] == 25


# ===================== Editar la recepción mueve el stock =====================


async def test_editar_la_linea_ajusta_el_lote_sin_duplicarlo(cliente, catalogo):
    """El lote se recalcula, no se acumula: si no, corregir un número dejaría
    el stock sumando el valor viejo y el nuevo."""
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    linea = await _recibir(cliente, recepcion, producto, unidad, 30, codigo_lote="L-1")

    r = await cliente.patch(
        f"{BASE}/recepciones-detalle/{linea}", json={"cantidad_ingresada": 20}
    )
    assert r.status_code == 200, r.text

    lotes = await _lotes(cliente, producto)
    assert len(lotes) == 1, "corregir la cantidad no puede abrir un lote nuevo"
    assert lotes[0]["cantidad"] == 20


async def test_dar_de_baja_la_linea_saca_el_stock(cliente, catalogo):
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    linea = await _recibir(cliente, recepcion, producto, unidad, 30, codigo_lote="L-1")

    r = await cliente.delete(f"{BASE}/recepciones-detalle/{linea}")
    assert r.status_code == 200, r.text

    assert (await _lotes(cliente, producto))[0]["cantidad"] == 0


async def test_mover_la_linea_a_otro_lote_no_deja_el_stock_duplicado(cliente, catalogo):
    """El lote que la línea deja atrás también se recalcula."""
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    linea = await _recibir(cliente, recepcion, producto, unidad, 30, codigo_lote="L-1")

    r = await cliente.patch(
        f"{BASE}/recepciones-detalle/{linea}", json={"codigo_lote": "L-2"}
    )
    assert r.status_code == 200, r.text

    por_codigo = {
        x["codigo_lote"]: x["cantidad"] for x in await _lotes(cliente, producto)
    }
    assert por_codigo == {"L-1": 0, "L-2": 30}


# ===================== La consulta de stock =====================


async def test_el_stock_del_almacen_suma_lo_recibido(cliente, catalogo):
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    await _recibir(cliente, recepcion, producto, unidad, 30, codigo_lote="L-1")

    fila = next(x for x in await _stock(cliente) if x["producto_id"] == producto)

    assert fila["disponible"] == 30


async def test_recibir_crea_la_ficha_del_producto(cliente, catalogo):
    """Registrar un lote es decir que ese producto vive en ese almacén. Sin
    ficha, el stock existía sin precio con el que venderlo."""
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    await _recibir(cliente, recepcion, producto, unidad, 30, codigo_lote="L-1")

    fila = next(x for x in await _stock(cliente) if x["producto_id"] == producto)

    assert fila["tiene_ficha"] is True
    assert fila["disponible"] == 30


async def test_la_ficha_creada_sola_no_pide_reposicion(cliente, catalogo):
    """Nadie decidió todavía cuánto hay que tener. Un mínimo inventado haría
    que cada cosa recién recibida pidiera reposición enseguida."""
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    await _recibir(cliente, recepcion, producto, unidad, 1, codigo_lote="L-1")

    fila = next(x for x in await _stock(cliente) if x["producto_id"] == producto)

    assert fila["stock_minimo"] == 0
    assert fila["bajo_minimo"] is False


async def test_la_ficha_creada_sola_queda_en_la_unidad_de_venta(cliente, catalogo):
    """Los lotes y el precio de tienda están en esa unidad: en otra, los tres
    números dejarían de ser comparables."""
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    await _recibir(cliente, recepcion, producto, unidad, 10, codigo_lote="L-1")

    ficha = await _ajustar_ficha(cliente, producto)

    assert ficha["unidad_medida_id"] == catalogo["unidad_venta"]


async def test_bajo_minimo_marca_lo_que_hay_que_reponer(cliente, catalogo):
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    await _recibir(cliente, recepcion, producto, unidad, 5, codigo_lote="L-1")
    await _ajustar_ficha(cliente, producto, stock_minimo=20)

    fila = next(x for x in await _stock(cliente) if x["producto_id"] == producto)

    assert fila["tiene_ficha"] is True
    assert fila["stock_minimo"] == 20
    assert fila["bajo_minimo"] is True


async def test_el_filtro_bajo_minimo_deja_fuera_lo_que_alcanza(cliente, catalogo):
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    await _recibir(cliente, recepcion, producto, unidad, 40, codigo_lote="L-1")
    await _ajustar_ficha(cliente, producto, stock_minimo=20)

    assert [
        x
        for x in await _stock(cliente, bajo_minimo=True)
        if x["producto_id"] == producto
    ] == []


async def test_el_stock_de_un_almacen_que_no_existe_es_404(cliente):
    """Un almacén inexistente y uno vacío son cosas distintas, y por el
    resultado no se podrían distinguir."""
    from uuid import uuid4

    r = await cliente.get(f"{BASE}/almacenes/{uuid4()}/stock")

    assert r.status_code == 404


# ===================== La guía en paquetes, el lote en unidad de venta =======


async def test_recibir_cajas_entra_al_stock_en_unidad_de_venta(cliente, catalogo):
    """La recepción viene por paquetes y el lote va en la unidad de venta del
    producto: 3 cajas de 12 son 36 unidades de stock, no 3."""
    caja = await _unidad(cliente, "Caja x12", "CAJA12", factor=12)
    recepcion, producto, _ = await _guia_con_linea(
        cliente, catalogo, cantidad=5, unidad=caja
    )

    await _recibir(cliente, recepcion, producto, caja, 3, codigo_lote="L-1")

    assert (await _lotes(cliente, producto))[0]["cantidad"] == 36


# ============ El stock cae en el almacén de esa recepción ============


async def _otro_almacen(cliente) -> str:
    """Un segundo almacén, bajo otro market.

    Con uno solo no se puede distinguir "el almacén correcto" de "el único que
    hay": cualquier bug que ignorara el almacén pasaría igual.
    """
    sede = (await cliente.get(f"{BASE}/markets")).json()["items"][0]["sede_id"]
    market = (
        await cliente.post(
            f"{BASE}/markets",
            json={"sede_id": sede, "nombre": "Market 2", "codigo": "MK2"},
        )
    ).json()["id"]
    r = await cliente.post(
        f"{BASE}/almacenes",
        json={"market_id": market, "nombre": "Anexo", "codigo": "ALM2"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _cadena_hasta_guia(cliente, almacen: str) -> str:
    """Una cadena completa cuyo requerimiento pide para `almacen`.

    No sirve reusar `_guia`: esa arma siempre la cadena del almacén de la
    fixture, y la recepción tiene que descargar en el almacén que pidió. Para
    probar dos almacenes hacen falta dos cadenas.
    """
    req = (
        await cliente.post(f"{BASE}/requerimientos", json={"almacen_id": almacen})
    ).json()["id"]
    await _aprobar(cliente, "requerimientos", req)

    pedido = (
        await cliente.post(f"{BASE}/pedidos", json={"requerimiento_id": req})
    ).json()["id"]
    await _aprobar(cliente, "pedidos", pedido)

    cot = (
        await cliente.post(
            f"{BASE}/cotizaciones",
            json={"pedido_id": pedido, "proveedor_id": await _proveedor(cliente)},
        )
    ).json()["id"]
    await _aprobar(cliente, "cotizaciones", cot)

    orden = (
        await cliente.post(f"{BASE}/ordenes-compra", json={"cotizacion_id": cot})
    ).json()["id"]
    await _aprobar(cliente, "ordenes-compra", orden)

    r = await cliente.post(f"{BASE}/guias-remision", json={"orden_compra_id": orden})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _recepcion_en(cliente, almacen: str, producto: str, unidad: str) -> str:
    """Guía con una línea de ese producto, recibida en `almacen`."""
    guia = await _cadena_hasta_guia(cliente, almacen)
    r = await cliente.post(
        f"{BASE}/guias-remision-detalle",
        json={
            "guia_remision_id": guia,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "cantidad": 50,
        },
    )
    assert r.status_code == 201, r.text
    r = await cliente.post(
        f"{BASE}/recepciones",
        json={"guia_remision_id": guia, "almacen_id": almacen},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _ajustar_ficha(cliente, producto, **cambios) -> dict:
    """Ajusta la ficha que la recepción creó sola.

    Ya no se da de alta a mano: registrar un lote la crea. Lo que un test
    quiere es fijarle un mínimo o mirarla, no inventarla.
    """
    ficha = (
        await cliente.get(f"{BASE}/productos-almacen", params={"producto_id": producto})
    ).json()["items"][0]
    if not cambios:
        return ficha
    r = await cliente.patch(f"{BASE}/productos-almacen/{ficha['id']}", json=cambios)
    assert r.status_code == 200, r.text
    return r.json()


async def _stock_de(cliente, almacen) -> list[dict]:
    r = await cliente.get(f"{BASE}/almacenes/{almacen}/stock")
    assert r.status_code == 200, r.text
    return r.json()


async def test_el_stock_cae_solo_en_el_almacen_de_la_recepcion(cliente, catalogo):
    """Recepcionar la guía carga el stock donde se recibió, y en ningún otro."""
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    recibe = await _almacen(cliente)
    otro = await _otro_almacen(cliente)

    await _recibir(cliente, recepcion, producto, unidad, 30, codigo_lote="L-1")

    en_el_que_recibe = await _stock_de(cliente, recibe)
    assert [(x["producto_id"], x["disponible"]) for x in en_el_que_recibe] == [
        (producto, 30)
    ]
    assert await _stock_de(cliente, otro) == [], "el otro almacén no recibió nada"


async def test_dos_guias_a_dos_almacenes_no_se_mezclan(cliente, catalogo):
    """Cada recepción carga su propio almacén: el stock no se suma en uno solo."""
    recepcion_a, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    almacen_a = await _almacen(cliente)
    almacen_b = await _otro_almacen(cliente)
    recepcion_b = await _recepcion_en(cliente, almacen_b, producto, unidad)

    await _recibir(cliente, recepcion_a, producto, unidad, 30, codigo_lote="L-A")
    await _recibir(cliente, recepcion_b, producto, unidad, 7, codigo_lote="L-B")

    assert [x["disponible"] for x in await _stock_de(cliente, almacen_a)] == [30]
    assert [x["disponible"] for x in await _stock_de(cliente, almacen_b)] == [7]


async def test_el_mismo_codigo_de_lote_en_dos_almacenes_son_dos_pilas(
    cliente, catalogo
):
    """El proveedor manda el mismo lote a dos tiendas: son dos bultos, no un
    choque de códigos ni un solo montón."""
    recepcion_a, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    almacen_a = await _almacen(cliente)
    almacen_b = await _otro_almacen(cliente)
    recepcion_b = await _recepcion_en(cliente, almacen_b, producto, unidad)

    await _recibir(cliente, recepcion_a, producto, unidad, 20, codigo_lote="LOTE-X")
    await _recibir(cliente, recepcion_b, producto, unidad, 5, codigo_lote="LOTE-X")

    por_almacen = {
        x["almacen_id"]: x["cantidad"] for x in await _lotes(cliente, producto)
    }
    assert por_almacen == {almacen_a: 20, almacen_b: 5}


# ============ Se recibe donde se pidió ============


async def test_recibir_en_un_almacen_que_no_pidio_es_409(cliente, catalogo):
    """Pedir para una tienda y descargar en otra dejaba el stock en un almacén
    que nunca lo pidió, y el requerimiento ATENDIDO igual."""
    guia = await _cadena_hasta_guia(cliente, await _almacen(cliente))
    otro = await _otro_almacen(cliente)

    r = await cliente.post(
        f"{BASE}/recepciones",
        json={"guia_remision_id": guia, "almacen_id": otro},
    )

    assert r.status_code == 409
    assert otro in r.json()["detail"]


async def test_mover_la_recepcion_a_otro_almacen_tambien_es_409(cliente, catalogo):
    """Si solo se validara el alta, quedaba el hueco de corregir después."""
    recepcion, _, _ = await _guia_con_linea(cliente, catalogo, 50)
    otro = await _otro_almacen(cliente)

    r = await cliente.patch(
        f"{BASE}/recepciones/{recepcion}", json={"almacen_id": otro}
    )

    assert r.status_code == 409


async def test_recibir_donde_se_pidio_pasa(cliente, catalogo):
    """La regla no puede volverse un candado: el caso normal sigue entrando."""
    almacen = await _almacen(cliente)
    guia = await _cadena_hasta_guia(cliente, almacen)

    r = await cliente.post(
        f"{BASE}/recepciones",
        json={"guia_remision_id": guia, "almacen_id": almacen},
    )

    assert r.status_code == 201, r.text


# ============ El precio de tienda sale del lote más caro ============


async def _ficha(cliente, almacen, producto, unidad, **extra) -> str:
    r = await cliente.post(
        f"{BASE}/productos-almacen",
        json={
            "almacen_id": almacen,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "stock_minimo": 1,
            **extra,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _ver_ficha(cliente, ficha) -> dict:
    r = await cliente.get(f"{BASE}/productos-almacen/{ficha}")
    assert r.status_code == 200, r.text
    return r.json()


async def _recibir_con_precio(
    cliente, recepcion, producto, unidad, ingresada, precio, codigo
) -> str:
    r = await cliente.post(
        f"{BASE}/recepciones-detalle",
        json={
            "recepcion_id": recepcion,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "cantidad_esperada": ingresada,
            "cantidad_ingresada": ingresada,
            "precio_unitario": precio,
            "codigo_lote": codigo,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_el_lote_guarda_lo_que_costo(cliente, catalogo):
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)

    await _recibir_con_precio(cliente, recepcion, producto, unidad, 10, "12.30", "L-1")

    assert (await _lotes(cliente, producto))[0]["precio_compra"] == "12.30"


async def test_el_costo_del_lote_va_por_unidad_de_venta(cliente, catalogo):
    """La recepción cobra por caja; el lote guarda por unidad de venta. Sin
    convertir, comparar el costo de dos lotes no significaría nada."""
    caja = await _unidad(cliente, "Caja x12", "CAJA12", factor=12)
    recepcion, producto, _ = await _guia_con_linea(
        cliente, catalogo, cantidad=5, unidad=caja
    )

    # 120.00 la caja de 12 son 10.00 la unidad.
    await _recibir_con_precio(cliente, recepcion, producto, caja, 3, "120.00", "L-1")

    assert (await _lotes(cliente, producto))[0]["precio_compra"] == "10.00"


async def test_el_precio_de_tienda_sale_del_lote_mas_caro(cliente, catalogo):
    """No se puede vender por debajo de lo que costó la partida que todavía
    está en el almacén."""
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    ficha = await _ficha(cliente, await _almacen(cliente), producto, unidad)

    await _recibir_con_precio(
        cliente, recepcion, producto, unidad, 10, "10.00", "BARATO"
    )

    # 10.00 con el 18.5% de la categoría de la fixture.
    assert (await _ver_ficha(cliente, ficha))["precio_venta_tienda"] == "11.85"


async def test_un_lote_mas_caro_sube_el_precio(cliente, catalogo):
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    almacen = await _almacen(cliente)
    ficha = await _ficha(cliente, almacen, producto, unidad)
    await _recibir_con_precio(
        cliente, recepcion, producto, unidad, 10, "10.00", "BARATO"
    )

    # Otra recepción: la línea es única por (recepción, producto), así que el
    # segundo lote del mismo producto llega por su propia cadena.
    otra = await _recepcion_en(cliente, almacen, producto, unidad)
    await _recibir_con_precio(cliente, otra, producto, unidad, 10, "20.00", "CARO")

    assert (await _ver_ficha(cliente, ficha))["precio_venta_tienda"] == "23.70"


async def test_un_lote_mas_barato_no_baja_el_precio(cliente, catalogo):
    """Manda el mayor: mientras quede stock del caro, ese es el piso."""
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    almacen = await _almacen(cliente)
    ficha = await _ficha(cliente, almacen, producto, unidad)
    await _recibir_con_precio(cliente, recepcion, producto, unidad, 10, "20.00", "CARO")

    otra = await _recepcion_en(cliente, almacen, producto, unidad)
    await _recibir_con_precio(cliente, otra, producto, unidad, 10, "10.00", "BARATO")

    assert (await _ver_ficha(cliente, ficha))["precio_venta_tienda"] == "23.70"


async def test_los_lotes_sin_stock_no_cuentan(cliente, catalogo):
    """El lote caro se agotó: el piso pasa a ser el del que queda."""
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    almacen = await _almacen(cliente)
    ficha = await _ficha(cliente, almacen, producto, unidad)
    caro = await _recibir_con_precio(
        cliente, recepcion, producto, unidad, 10, "20.00", "CARO"
    )
    otra = await _recepcion_en(cliente, almacen, producto, unidad)
    await _recibir_con_precio(cliente, otra, producto, unidad, 10, "10.00", "BARATO")

    r = await cliente.delete(f"{BASE}/recepciones-detalle/{caro}")
    assert r.status_code == 200, r.text

    assert (await _ver_ficha(cliente, ficha))["precio_venta_tienda"] == "11.85"


async def test_sin_ningun_lote_con_stock_el_precio_se_conserva(cliente, catalogo):
    """Quedarse sin mercadería no es motivo para perder el precio con el que se
    venía vendiendo: no hay máximo que tomar, así que no se toca."""
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    ficha = await _ficha(cliente, await _almacen(cliente), producto, unidad)
    linea = await _recibir_con_precio(
        cliente, recepcion, producto, unidad, 10, "10.00", "L-1"
    )

    r = await cliente.delete(f"{BASE}/recepciones-detalle/{linea}")
    assert r.status_code == 200, r.text

    assert (await _ver_ficha(cliente, ficha))["precio_venta_tienda"] == "11.85"


async def test_el_precio_manual_no_lo_pisa_la_recepcion(cliente, catalogo):
    """Una promoción es una decisión comercial, no un dato que corregir."""
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    ficha = await _ficha(
        cliente,
        await _almacen(cliente),
        producto,
        unidad,
        precio_venta_tienda="5.00",
        precio_manual=True,
    )

    await _recibir_con_precio(cliente, recepcion, producto, unidad, 10, "10.00", "L-1")

    assert (await _ver_ficha(cliente, ficha))["precio_venta_tienda"] == "5.00"


async def test_quitar_la_marca_manual_devuelve_al_calculado(cliente, catalogo):
    """Si solo se guardara el `False`, el precio se quedaría en el de la
    promoción hasta la próxima recepción."""
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    ficha = await _ficha(
        cliente,
        await _almacen(cliente),
        producto,
        unidad,
        precio_venta_tienda="5.00",
        precio_manual=True,
    )
    await _recibir_con_precio(cliente, recepcion, producto, unidad, 10, "10.00", "L-1")

    r = await cliente.patch(
        f"{BASE}/productos-almacen/{ficha}", json={"precio_manual": False}
    )

    assert r.status_code == 200, r.text
    assert r.json()["precio_venta_tienda"] == "11.85"


async def test_marcar_manual_sin_decir_el_precio_es_422(cliente, catalogo):
    """Dejaría la ficha congelada en cero, y la sincronización ya no la
    corregiría."""
    _, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)

    r = await cliente.post(
        f"{BASE}/productos-almacen",
        json={
            "almacen_id": await _almacen(cliente),
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "precio_manual": True,
        },
    )

    assert r.status_code == 422


async def test_la_ficha_sin_stock_arranca_en_cero(cliente, catalogo):
    """Se crea antes de que entre mercadería: no hay lote del que sacar el
    máximo, y la primera recepción lo deja en su valor."""
    _, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)

    ficha = await _ficha(cliente, await _almacen(cliente), producto, unidad)

    assert (await _ver_ficha(cliente, ficha))["precio_venta_tienda"] == "0.00"


async def test_cargar_un_lote_a_mano_tambien_crea_la_ficha(cliente, catalogo):
    """El alta manual del lote existe para el ajuste y para el caso sin
    recepción: también deja el producto consultable y con precio."""
    _, producto, _ = await _guia_con_linea(cliente, catalogo, 50)
    almacen = await _almacen(cliente)
    r = await cliente.post(
        f"{BASE}/productos-lote",
        json={
            "almacen_id": almacen,
            "producto_id": producto,
            "fecha_ingreso": "2026-08-12",
            "cantidad": 10,
            "precio_compra": "10.00",
            "codigo_lote": "MANUAL-1",
        },
    )
    assert r.status_code == 201, r.text

    fila = next(x for x in await _stock_de(cliente, almacen) if x["producto_id"] == producto)

    assert fila["tiene_ficha"] is True
    assert fila["disponible"] == 10


async def test_la_ficha_dada_de_baja_se_reactiva(cliente, catalogo):
    """La unicidad de la tabla no distingue las dadas de baja: insertar una
    segunda chocaría contra el índice."""
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    almacen = await _almacen(cliente)
    await _recibir(cliente, recepcion, producto, unidad, 10, codigo_lote="L-1")
    ficha = await _ajustar_ficha(cliente, producto)
    assert (await cliente.delete(f"{BASE}/productos-almacen/{ficha['id']}")).status_code == 200

    otra = await _recepcion_en(cliente, almacen, producto, unidad)
    r = await cliente.post(
        f"{BASE}/recepciones-detalle",
        json={
            "recepcion_id": otra,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "cantidad_esperada": 5,
            "cantidad_ingresada": 5,
            "codigo_lote": "L-2",
        },
    )

    assert r.status_code == 201, r.text
    assert (await _ajustar_ficha(cliente, producto))["id"] == ficha["id"]
