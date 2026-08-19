"""Aprobar un documento genera el siguiente de la cadena.

    requerimiento → pedido → cotización → orden de compra → guía de remisión

`test_cadena_compras.py` prueba la mitad de la regla —un documento solo nace de
un padre aprobado— trabajando solo con cabeceras. Acá se prueba la otra mitad,
que sí necesita líneas y productos: aprobar **crea** al sucesor y le copia el
detalle.

El caso del pedido va aparte porque es el único que genera varios sucesores:
una cotización por proveedor, con lo que cada uno puede atender.
"""

from __future__ import annotations

from app.modules.movimientos.constantes import (
    CODIGO_APROBADO,
    CODIGO_PENDIENTE,
)
from tests.conftest import producto_valido

BASE = "/api/v1"


# ===================== Utilidades =====================


async def _estado(cliente, codigo: str) -> str:
    items = (
        await cliente.get(f"{BASE}/estados", params={"codigo": codigo})
    ).json()["items"]
    assert items, f"falta el estado canónico '{codigo}'"
    return items[0]["id"]


async def _aprobar(cliente, recurso: str, registro_id: str):
    r = await cliente.patch(
        f"{BASE}/{recurso}/{registro_id}",
        json={"estado_id": await _estado(cliente, CODIGO_APROBADO)},
    )
    return r


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


async def _producto(cliente, catalogo: dict, sku: str) -> str:
    r = await cliente.post(f"{BASE}/productos", json=producto_valido(catalogo, sku))
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _proveedor(cliente, ruc: str, razon: str = "PROVEEDORA S.A.C.") -> str:
    r = await cliente.post(
        f"{BASE}/empresas",
        json={
            "razon_social": razon,
            "ruc": ruc,
            "ubigeo_sunat": "150101",
            "estado": "ACTIVO",
            "es_proveedor": True,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _asignar(cliente, empresa_id: str, producto_id: str, dias: int) -> None:
    r = await cliente.put(
        f"{BASE}/empresas/{empresa_id}/productos/{producto_id}",
        json={"tiempo_atencion": dias},
    )
    assert r.status_code in (200, 201), r.text


async def _requerimiento_con_lineas(cliente, catalogo, productos) -> str:
    """Un requerimiento pendiente con una línea por producto."""
    almacen = await _almacen(cliente)
    req = (
        await cliente.post(
            f"{BASE}/requerimientos",
            json={
                "almacen_id": almacen,
                "estado_id": await _estado(cliente, CODIGO_PENDIENTE),
            },
        )
    ).json()["id"]

    for i, producto_id in enumerate(productos, start=1):
        r = await cliente.post(
            f"{BASE}/requerimientos-detalle",
            json={
                "requerimiento_id": req,
                "producto_id": producto_id,
                "unidad_medida_id": catalogo["unidad_compra"],
                "cantidad": i * 10,
            },
        )
        assert r.status_code == 201, r.text
    return req


async def _hijos(cliente, recurso: str, campo: str, padre_id: str) -> list[dict]:
    r = await cliente.get(f"{BASE}/{recurso}", params={campo: padre_id})
    assert r.status_code == 200, r.text
    return r.json()["items"]


# ===================== Requerimiento → pedido =====================


async def test_aprobar_el_requerimiento_genera_el_pedido(cliente, catalogo):
    producto = await _producto(cliente, catalogo, "ARR-001")
    req = await _requerimiento_con_lineas(cliente, catalogo, [producto])

    assert (await _aprobar(cliente, "requerimientos", req)).status_code == 200

    pedidos = await _hijos(cliente, "pedidos", "requerimiento_id", req)
    assert len(pedidos) == 1, "aprobar el requerimiento tiene que abrir el pedido"
    assert pedidos[0]["fecha"] is not None


async def test_el_pedido_generado_nace_pendiente(cliente, catalogo):
    """Generarlo es proponer el paso siguiente, no darlo por bueno."""
    producto = await _producto(cliente, catalogo, "ARR-002")
    req = await _requerimiento_con_lineas(cliente, catalogo, [producto])

    await _aprobar(cliente, "requerimientos", req)

    pedido = (await _hijos(cliente, "pedidos", "requerimiento_id", req))[0]
    assert pedido["estado_id"] == await _estado(cliente, CODIGO_PENDIENTE)


async def test_el_pedido_hereda_las_lineas_del_requerimiento(cliente, catalogo):
    """Si no, el documento generado sería una cabecera vacía y habría que
    volver a teclear lo mismo."""
    uno = await _producto(cliente, catalogo, "ARR-003")
    dos = await _producto(cliente, catalogo, "ARR-004")
    req = await _requerimiento_con_lineas(cliente, catalogo, [uno, dos])

    await _aprobar(cliente, "requerimientos", req)

    pedido = (await _hijos(cliente, "pedidos", "requerimiento_id", req))[0]
    lineas = await _hijos(cliente, "pedidos-detalle", "pedido_id", pedido["id"])
    assert {(x["producto_id"], x["cantidad"]) for x in lineas} == {(uno, 10), (dos, 20)}


async def test_reaprobar_no_duplica_el_pedido(cliente, catalogo):
    """El PATCH puede repetirse; la cadena no tiene por qué duplicarse."""
    producto = await _producto(cliente, catalogo, "ARR-005")
    req = await _requerimiento_con_lineas(cliente, catalogo, [producto])

    await _aprobar(cliente, "requerimientos", req)
    await _aprobar(cliente, "requerimientos", req)

    assert len(await _hijos(cliente, "pedidos", "requerimiento_id", req)) == 1


async def test_editar_sin_aprobar_no_genera_nada(cliente, catalogo):
    producto = await _producto(cliente, catalogo, "ARR-006")
    req = await _requerimiento_con_lineas(cliente, catalogo, [producto])

    r = await cliente.patch(f"{BASE}/requerimientos/{req}", json={"fecha": "2026-08-20"})

    assert r.status_code == 200, r.text
    assert await _hijos(cliente, "pedidos", "requerimiento_id", req) == []


# ===================== Pedido → cotizaciones =====================


async def test_aprobar_el_pedido_abre_una_cotizacion_por_proveedor(cliente, catalogo):
    """Cotizar es pedirle precio a varios: una sola elegiría por el operador."""
    producto = await _producto(cliente, catalogo, "ARR-010")
    rapido = await _proveedor(cliente, "20552103816", "RAPIDA S.A.C.")
    lento = await _proveedor(cliente, "20100070970", "LENTA S.A.C.")
    await _asignar(cliente, rapido, producto, 2)
    await _asignar(cliente, lento, producto, 9)

    req = await _requerimiento_con_lineas(cliente, catalogo, [producto])
    await _aprobar(cliente, "requerimientos", req)
    pedido = (await _hijos(cliente, "pedidos", "requerimiento_id", req))[0]

    assert (await _aprobar(cliente, "pedidos", pedido["id"])).status_code == 200

    cotizaciones = await _hijos(cliente, "cotizaciones", "pedido_id", pedido["id"])
    assert {c["proveedor_id"] for c in cotizaciones} == {rapido, lento}


async def test_cada_cotizacion_lleva_el_plazo_de_su_proveedor(cliente, catalogo):
    producto = await _producto(cliente, catalogo, "ARR-011")
    rapido = await _proveedor(cliente, "20552103816", "RAPIDA S.A.C.")
    lento = await _proveedor(cliente, "20100070970", "LENTA S.A.C.")
    await _asignar(cliente, rapido, producto, 2)
    await _asignar(cliente, lento, producto, 9)

    req = await _requerimiento_con_lineas(cliente, catalogo, [producto])
    await _aprobar(cliente, "requerimientos", req)
    pedido = (await _hijos(cliente, "pedidos", "requerimiento_id", req))[0]
    await _aprobar(cliente, "pedidos", pedido["id"])

    cotizaciones = await _hijos(cliente, "cotizaciones", "pedido_id", pedido["id"])
    plazos = {c["proveedor_id"]: c["tiempo_atencion"] for c in cotizaciones}
    assert plazos == {rapido: 2, lento: 9}


async def test_la_cotizacion_solo_lleva_lo_que_ese_proveedor_distribuye(
    cliente, catalogo
):
    """Pedirle precio por algo que no vende no es una cotización, es ruido."""
    arroz = await _producto(cliente, catalogo, "ARR-012")
    azucar = await _producto(cliente, catalogo, "AZU-012")
    ambos = await _proveedor(cliente, "20552103816", "COMPLETA S.A.C.")
    solo_arroz = await _proveedor(cliente, "20100070970", "PARCIAL S.A.C.")
    await _asignar(cliente, ambos, arroz, 3)
    await _asignar(cliente, ambos, azucar, 5)
    await _asignar(cliente, solo_arroz, arroz, 1)

    req = await _requerimiento_con_lineas(cliente, catalogo, [arroz, azucar])
    await _aprobar(cliente, "requerimientos", req)
    pedido = (await _hijos(cliente, "pedidos", "requerimiento_id", req))[0]
    await _aprobar(cliente, "pedidos", pedido["id"])

    cotizaciones = await _hijos(cliente, "cotizaciones", "pedido_id", pedido["id"])
    por_proveedor = {c["proveedor_id"]: c["id"] for c in cotizaciones}

    completas = await _hijos(
        cliente, "cotizaciones-detalle", "cotizacion_id", por_proveedor[ambos]
    )
    parciales = await _hijos(
        cliente, "cotizaciones-detalle", "cotizacion_id", por_proveedor[solo_arroz]
    )
    assert {x["producto_id"] for x in completas} == {arroz, azucar}
    assert {x["producto_id"] for x in parciales} == {arroz}
    # El plazo del que lleva las dos es el del producto más lento: el pedido no
    # está atendido hasta que llega la última línea.
    assert next(c for c in cotizaciones if c["proveedor_id"] == ambos)[
        "tiempo_atencion"
    ] == 5


async def test_la_cotizacion_generada_arranca_sin_precio(cliente, catalogo):
    """El pedido no mueve dinero; el precio lo pone el proveedor."""
    producto = await _producto(cliente, catalogo, "ARR-013")
    proveedor = await _proveedor(cliente, "20552103816")
    await _asignar(cliente, proveedor, producto, 4)

    req = await _requerimiento_con_lineas(cliente, catalogo, [producto])
    await _aprobar(cliente, "requerimientos", req)
    pedido = (await _hijos(cliente, "pedidos", "requerimiento_id", req))[0]
    await _aprobar(cliente, "pedidos", pedido["id"])

    cotizacion = (await _hijos(cliente, "cotizaciones", "pedido_id", pedido["id"]))[0]
    lineas = await _hijos(
        cliente, "cotizaciones-detalle", "cotizacion_id", cotizacion["id"]
    )
    assert all(float(x["precio_unitario"]) == 0 for x in lineas)
    assert float(cotizacion["monto_total"]) == 0


async def test_sin_proveedores_asignados_no_se_puede_aprobar_el_pedido(
    cliente, catalogo
):
    """Aprobarlo lo dejaría sin a quién pedirle precio y sin decir por qué."""
    producto = await _producto(cliente, catalogo, "ARR-014")
    req = await _requerimiento_con_lineas(cliente, catalogo, [producto])
    await _aprobar(cliente, "requerimientos", req)
    pedido = (await _hijos(cliente, "pedidos", "requerimiento_id", req))[0]

    r = await _aprobar(cliente, "pedidos", pedido["id"])

    assert r.status_code == 409
    assert "Ningún proveedor" in r.json()["detail"]


async def test_el_pedido_rechazado_no_queda_aprobado(cliente, catalogo):
    """Aprobar y generar entran juntos o no entra ninguno."""
    producto = await _producto(cliente, catalogo, "ARR-015")
    req = await _requerimiento_con_lineas(cliente, catalogo, [producto])
    await _aprobar(cliente, "requerimientos", req)
    pedido = (await _hijos(cliente, "pedidos", "requerimiento_id", req))[0]

    await _aprobar(cliente, "pedidos", pedido["id"])

    actual = (await cliente.get(f"{BASE}/pedidos/{pedido['id']}")).json()
    assert actual["estado_id"] == await _estado(cliente, CODIGO_PENDIENTE)


async def test_un_pedido_sin_lineas_se_aprueba_sin_generar_nada(cliente, catalogo):
    """Aprobar la cabecera y cargar el detalle después es legítimo."""
    req = await _requerimiento_con_lineas(cliente, catalogo, [])
    await _aprobar(cliente, "requerimientos", req)
    pedido = (
        await cliente.post(
            f"{BASE}/pedidos",
            json={
                "requerimiento_id": req,
                "estado_id": await _estado(cliente, CODIGO_PENDIENTE),
            },
        )
    ).json()["id"]

    r = await _aprobar(cliente, "pedidos", pedido)

    assert r.status_code == 200, r.text
    assert await _hijos(cliente, "cotizaciones", "pedido_id", pedido) == []


# ===================== Cotización → orden, y orden → guía =====================


async def _cotizacion_con_precios(cliente, catalogo, precio: str = "12.50") -> dict:
    """Una cotización pendiente, con su línea ya valorizada."""
    producto = await _producto(cliente, catalogo, "ARR-020")
    proveedor = await _proveedor(cliente, "20552103816")
    await _asignar(cliente, proveedor, producto, 3)

    req = await _requerimiento_con_lineas(cliente, catalogo, [producto])
    await _aprobar(cliente, "requerimientos", req)
    pedido = (await _hijos(cliente, "pedidos", "requerimiento_id", req))[0]
    await _aprobar(cliente, "pedidos", pedido["id"])

    cotizacion = (await _hijos(cliente, "cotizaciones", "pedido_id", pedido["id"]))[0]
    linea = (
        await _hijos(cliente, "cotizaciones-detalle", "cotizacion_id", cotizacion["id"])
    )[0]
    r = await cliente.patch(
        f"{BASE}/cotizaciones-detalle/{linea['id']}", json={"precio_unitario": precio}
    )
    assert r.status_code == 200, r.text
    return cotizacion


async def test_aprobar_la_cotizacion_emite_la_orden_con_sus_precios(cliente, catalogo):
    """Aprobar una cotización es elegir a ese proveedor a ese precio."""
    cotizacion = await _cotizacion_con_precios(cliente, catalogo, "12.50")

    assert (await _aprobar(cliente, "cotizaciones", cotizacion["id"])).status_code == 200

    ordenes = await _hijos(cliente, "ordenes-compra", "cotizacion_id", cotizacion["id"])
    assert len(ordenes) == 1
    lineas = await _hijos(
        cliente, "ordenes-compra-detalle", "orden_compra_id", ordenes[0]["id"]
    )
    assert [x["precio_unitario"] for x in lineas] == ["12.50"]
    # 10 unidades a 12.50: el total del documento generado tiene que cuadrar
    # desde el primer momento, no cuando alguien toque una línea.
    assert float(ordenes[0]["monto_total"]) == 125.0


async def test_aprobar_la_orden_abre_la_guia_con_las_cantidades(cliente, catalogo):
    """La guía no mueve dinero: lleva lo que se espera recibir."""
    cotizacion = await _cotizacion_con_precios(cliente, catalogo)
    await _aprobar(cliente, "cotizaciones", cotizacion["id"])
    orden = (await _hijos(cliente, "ordenes-compra", "cotizacion_id", cotizacion["id"]))[
        0
    ]

    assert (await _aprobar(cliente, "ordenes-compra", orden["id"])).status_code == 200

    guias = await _hijos(cliente, "guias-remision", "orden_compra_id", orden["id"])
    assert len(guias) == 1
    lineas = await _hijos(
        cliente, "guias-remision-detalle", "guia_remision_id", guias[0]["id"]
    )
    assert [x["cantidad"] for x in lineas] == [10]


async def test_la_cadena_entera_sale_de_aprobar_cuatro_veces(cliente, catalogo):
    """El caso que da sentido a todo esto: cuatro PATCH y la cadena existe."""
    producto = await _producto(cliente, catalogo, "ARR-030")
    proveedor = await _proveedor(cliente, "20552103816")
    await _asignar(cliente, proveedor, producto, 3)
    req = await _requerimiento_con_lineas(cliente, catalogo, [producto])

    await _aprobar(cliente, "requerimientos", req)
    pedido = (await _hijos(cliente, "pedidos", "requerimiento_id", req))[0]
    await _aprobar(cliente, "pedidos", pedido["id"])
    cotizacion = (await _hijos(cliente, "cotizaciones", "pedido_id", pedido["id"]))[0]
    await _aprobar(cliente, "cotizaciones", cotizacion["id"])
    orden = (await _hijos(cliente, "ordenes-compra", "cotizacion_id", cotizacion["id"]))[
        0
    ]
    await _aprobar(cliente, "ordenes-compra", orden["id"])

    guias = await _hijos(cliente, "guias-remision", "orden_compra_id", orden["id"])
    assert len(guias) == 1, "de aprobar la orden sale la guía, y con eso la cadena entera"
