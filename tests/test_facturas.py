"""La factura del proveedor contra una orden de compra.

Es el documento del proveedor y no uno nuestro: por eso lleva su serie y su
correlativo, y por eso su monto no tiene que coincidir con el de la orden. Lo
que sí se comprueba es que cobre algo que se pidió —una orden visada, del
proveedor que la recibió, y con la guía que le corresponda—.

Los helpers de la cadena se reutilizan de `test_cadena_compras`: montar una
orden aprobada es exactamente lo mismo acá.
"""

from __future__ import annotations

from uuid import uuid4

from app.modules.movimientos.constantes import CODIGO_PENDIENTE
from tests.test_cadena_compras import (
    BASE,
    _almacen,
    _cotizacion,
    _estado,
    _guia,
    _orden,
    _proveedor,
)


def _factura(orden, proveedor, **extra) -> dict:
    return {
        "proveedor_id": proveedor,
        "serie": "F001",
        "correlativo": "00001234",
        "orden_compra_id": orden,
        "monto_total": "1000.00",
        "fecha_emision": "2026-08-01",
        "fecha_vencimiento": "2026-08-31",
        **extra,
    }


async def _crear(cliente, orden, proveedor, **extra):
    return await cliente.post(
        f"{BASE}/facturas", json=_factura(orden, proveedor, **extra)
    )


# ===================== El alta =====================


async def test_facturar_una_orden_aprobada(cliente):
    """El módulo no tenía servicio ni router: no había forma de dar de alta
    una factura."""
    orden = await _orden(cliente)

    r = await _crear(cliente, orden, await _proveedor(cliente))

    assert r.status_code == 201, r.text
    assert r.json()["serie"] == "F001"
    assert r.json()["correlativo"] == "00001234"


async def test_la_factura_nace_pendiente(cliente):
    orden = await _orden(cliente)

    r = await _crear(cliente, orden, await _proveedor(cliente))

    assert r.json()["estado_id"] == await _estado(cliente, CODIGO_PENDIENTE)


async def test_el_monto_pago_arranca_en_cero(cliente):
    """Lo normal es registrar la factura antes de pagarla."""
    orden = await _orden(cliente)

    r = await _crear(cliente, orden, await _proveedor(cliente))

    assert r.json()["monto_pago"] == "0.00"


async def test_la_misma_factura_dos_veces_es_409(cliente):
    """Serie y correlativo identifican el comprobante dentro del proveedor:
    repetirlo es cargar dos veces el mismo papel."""
    orden = await _orden(cliente)
    proveedor = await _proveedor(cliente)
    assert (await _crear(cliente, orden, proveedor)).status_code == 201

    r = await _crear(cliente, orden, proveedor)

    assert r.status_code == 409


async def test_el_mismo_numero_de_otro_proveedor_si_entra(cliente):
    """Cada proveedor lleva su propia numeración: F001-00001234 existe en
    todos, y no son la misma factura."""
    orden = await _orden(cliente)
    assert (await _crear(cliente, orden, await _proveedor(cliente))).status_code == 201
    otro = await _proveedor(cliente, "20100070970")

    r = await cliente.post(
        f"{BASE}/facturas",
        json={
            **_factura(orden, otro),
            # La orden es de otro proveedor, así que se factura la suya.
            "orden_compra_id": orden,
        },
    )

    # La orden sigue siendo del primero: lo que corta es el proveedor, no el
    # número. Que el número no sea el problema se ve en el mensaje.
    assert r.status_code == 409
    assert "proveedor" in r.json()["detail"]


# ===================== Contra qué se factura =====================


async def test_facturar_una_orden_pendiente_es_409(cliente):
    """Nadie visó esa orden todavía."""
    cot = await _cotizacion(cliente)
    orden = (
        await cliente.post(f"{BASE}/ordenes-compra", json={"cotizacion_id": cot})
    ).json()["id"]

    r = await _crear(cliente, orden, await _proveedor(cliente))

    assert r.status_code == 409
    assert CODIGO_PENDIENTE in r.json()["detail"]


async def test_facturar_una_orden_atendida_si_entra(cliente):
    """La factura suele llegar con la mercadería o después, y recepcionar deja
    la orden en ATENDIDO: exigir APROBADO habría bloqueado el caso normal."""
    guia = await _guia(cliente)
    orden = (await cliente.get(f"{BASE}/guias-remision/{guia}")).json()[
        "orden_compra_id"
    ]
    r = await cliente.post(
        f"{BASE}/recepciones",
        json={"guia_remision_id": guia, "almacen_id": await _almacen(cliente)},
    )
    assert r.status_code == 201, r.text

    r = await _crear(cliente, orden, await _proveedor(cliente), guia_remision_id=guia)

    assert r.status_code == 201, r.text


async def test_facturar_una_orden_que_no_existe_es_400(cliente):
    r = await _crear(cliente, str(uuid4()), await _proveedor(cliente))

    assert r.status_code == 400
    assert "no existe" in r.json()["detail"]


async def test_solo_factura_el_proveedor_de_la_orden(cliente):
    """La orden no lleva `proveedor_id`: sale de su cotización."""
    orden = await _orden(cliente)
    ajeno = await _proveedor(cliente, "20100070970")

    r = await _crear(cliente, orden, ajeno)

    assert r.status_code == 409
    assert "Solo factura quien recibió la orden" in r.json()["detail"]


async def test_la_guia_tiene_que_ser_de_esa_orden(cliente):
    """Sin esto se podría colgar la factura de una guía ajena."""
    orden = await _orden(cliente)
    guia_ajena = await _guia(cliente)

    r = await _crear(
        cliente, orden, await _proveedor(cliente), guia_remision_id=guia_ajena
    )

    assert r.status_code == 409
    assert "pertenece a la orden" in r.json()["detail"]


# ===================== El monto contra la orden =====================


async def test_la_factura_avisa_cuando_no_cobra_lo_que_la_orden_comprometia(cliente):
    """No se bloquea —entregas parciales y fletes son legítimos— pero quien
    revisa tiene que verlo sin comparar a ojo."""
    orden = await _orden(cliente)

    r = await _crear(cliente, orden, await _proveedor(cliente), monto_total="1234.00")

    assert r.status_code == 201, r.text
    # La orden nace con total en cero: sus líneas lo van sumando.
    assert r.json()["monto_orden"] == "0.00"
    assert r.json()["difiere_de_la_orden"] is True


async def test_cuando_coincide_no_avisa(cliente):
    orden = await _orden(cliente)

    r = await _crear(cliente, orden, await _proveedor(cliente), monto_total="0")

    assert r.status_code == 201, r.text
    assert r.json()["difiere_de_la_orden"] is False


async def test_el_listado_tambien_trae_la_comparacion(cliente):
    """Se resuelve en una consulta para todo el listado, no una por fila."""
    orden = await _orden(cliente)
    await _crear(cliente, orden, await _proveedor(cliente), monto_total="500.00")

    items = (await cliente.get(f"{BASE}/facturas")).json()["items"]

    assert [x["difiere_de_la_orden"] for x in items] == [True]
    assert [x["monto_orden"] for x in items] == ["0.00"]


# ===================== Validaciones de carga =====================


async def test_vencimiento_anterior_a_la_emision_es_422(cliente):
    orden = await _orden(cliente)

    r = await _crear(
        cliente,
        orden,
        await _proveedor(cliente),
        fecha_emision="2026-08-31",
        fecha_vencimiento="2026-08-01",
    )

    assert r.status_code == 422


async def test_monto_negativo_es_422(cliente):
    """`Field(min=0)` no era una restricción de Pydantic: los montos
    negativos entraban sin que nada los mirara."""
    orden = await _orden(cliente)

    r = await _crear(cliente, orden, await _proveedor(cliente), monto_total="-1.00")

    assert r.status_code == 422


async def test_pagar_mas_de_lo_facturado_es_422(cliente):
    orden = await _orden(cliente)

    r = await _crear(
        cliente,
        orden,
        await _proveedor(cliente),
        monto_total="100.00",
        monto_pago="150.00",
    )

    assert r.status_code == 422


# ===================== La edición revalida =====================


async def test_mover_la_factura_a_otro_proveedor_es_409(cliente):
    """Si solo se validara el alta, quedaba el hueco de corregir después."""
    orden = await _orden(cliente)
    factura = (await _crear(cliente, orden, await _proveedor(cliente))).json()["id"]
    ajeno = await _proveedor(cliente, "20100070970")

    r = await cliente.patch(f"{BASE}/facturas/{factura}", json={"proveedor_id": ajeno})

    assert r.status_code == 409


async def test_registrar_un_pago_actualiza_la_factura(cliente):
    orden = await _orden(cliente)
    factura = (await _crear(cliente, orden, await _proveedor(cliente))).json()["id"]

    r = await cliente.patch(f"{BASE}/facturas/{factura}", json={"monto_pago": "400.00"})

    assert r.status_code == 200, r.text
    assert r.json()["monto_pago"] == "400.00"


# ===================== La recepción puede apuntar a la factura =====================


async def test_la_recepcion_puede_referenciar_la_factura(cliente):
    """La columna existía apuntando al vacío: no había tabla contra la cual
    atarla, así que aceptaba cualquier uuid."""
    guia = await _guia(cliente)
    orden = (await cliente.get(f"{BASE}/guias-remision/{guia}")).json()[
        "orden_compra_id"
    ]
    factura = (
        await _crear(cliente, orden, await _proveedor(cliente), guia_remision_id=guia)
    ).json()["id"]

    r = await cliente.post(
        f"{BASE}/recepciones",
        json={
            "guia_remision_id": guia,
            "almacen_id": await _almacen(cliente),
            "factura_id": factura,
        },
    )

    assert r.status_code == 201, r.text
    assert r.json()["factura_id"] == factura


async def test_una_factura_inexistente_en_la_recepcion_es_400(cliente):
    """Antes entraba cualquier uuid: la columna no tenía FK."""
    guia = await _guia(cliente)

    r = await cliente.post(
        f"{BASE}/recepciones",
        json={
            "guia_remision_id": guia,
            "almacen_id": await _almacen(cliente),
            "factura_id": str(uuid4()),
        },
    )

    assert r.status_code == 400
