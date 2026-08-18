"""Las reglas que hacen avanzar la cadena de compras.

    requerimiento → pedido → cotización → orden de compra → guía → recepción

Cada eslabón solo nace del anterior **aprobado**, y la recepción cierra todo:
la guía queda `RECEPCIONADO` y lo anterior `ATENDIDO`.

Estos tests trabajan solo con cabeceras, sin productos ni líneas: lo que se
prueba acá es la máquina de estados, y meter el catálogo de productos de por
medio solo añadiría formas de fallar que no tienen que ver con la regla.
"""

from __future__ import annotations

import pytest

from app.modules.movimientos.constantes import (
    CODIGO_APROBADO,
    CODIGO_ATENDIDO,
    CODIGO_PENDIENTE,
    CODIGO_RECEPCIONADO,
)

BASE = "/api/v1"


# ===================== Utilidades =====================


async def _estado(cliente, codigo: str) -> str:
    """El id de un estado canónico. Los siembra la migración."""
    r = await cliente.get(f"{BASE}/estados", params={"codigo": codigo})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items, f"falta el estado canónico '{codigo}'"
    return items[0]["id"]


async def _almacen(cliente) -> str:
    """El almacén del test, creándolo la primera vez.

    Se reutiliza a propósito: varios helpers lo piden dentro del mismo test y
    zona, sede y market tienen código único, así que crear uno nuevo cada vez
    chocaba con un 409 que no tenía nada que ver con lo que se estaba probando.
    """
    existentes = (await cliente.get(f"{BASE}/almacenes")).json()["items"]
    if existentes:
        return existentes[0]["id"]

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


async def _proveedor(cliente, ruc="20552103816") -> str:
    """El proveedor de ese RUC, creándolo si no está.

    Reutiliza igual que `_almacen`: un test que arma dos cadenas pide dos veces
    el mismo proveedor, y el RUC es único.
    """
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
    if r.status_code == 201:
        return r.json()["id"]

    assert r.status_code == 409, r.text
    existentes = (await cliente.get(f"{BASE}/empresas")).json()["items"]
    return next(e["id"] for e in existentes if e["ruc"] == ruc)


async def _aprobar(cliente, recurso: str, registro_id: str) -> None:
    """Deja el documento en APROBADO, que es lo que habilita el siguiente."""
    aprobado = await _estado(cliente, CODIGO_APROBADO)
    r = await cliente.patch(
        f"{BASE}/{recurso}/{registro_id}", json={"estado_id": aprobado}
    )
    assert r.status_code == 200, r.text


async def _codigo_de(cliente, recurso: str, registro_id: str) -> str:
    """El `codigo` del estado en que quedó el documento."""
    documento = (await cliente.get(f"{BASE}/{recurso}/{registro_id}")).json()
    estado = (await cliente.get(f"{BASE}/estados/{documento['estado_id']}")).json()
    return estado["codigo"]


async def _requerimiento(cliente, aprobado: bool = True) -> str:
    almacen = await _almacen(cliente)
    r = await cliente.post(
        f"{BASE}/requerimientos",
        json={
            "almacen_id": almacen,
            "estado_id": await _estado(cliente, CODIGO_PENDIENTE),
        },
    )
    assert r.status_code == 201, r.text
    req = r.json()["id"]
    if aprobado:
        await _aprobar(cliente, "requerimientos", req)
    return req


async def _pedido(cliente, aprobado: bool = True) -> str:
    req = await _requerimiento(cliente)
    r = await cliente.post(
        f"{BASE}/pedidos",
        json={
            "requerimiento_id": req,
            "estado_id": await _estado(cliente, CODIGO_PENDIENTE),
        },
    )
    assert r.status_code == 201, r.text
    pedido = r.json()["id"]
    if aprobado:
        await _aprobar(cliente, "pedidos", pedido)
    return pedido


async def _cotizacion(cliente, aprobada: bool = True) -> str:
    pedido = await _pedido(cliente)
    r = await cliente.post(
        f"{BASE}/cotizaciones",
        json={
            "pedido_id": pedido,
            "proveedor_id": await _proveedor(cliente),
            "estado_id": await _estado(cliente, CODIGO_PENDIENTE),
        },
    )
    assert r.status_code == 201, r.text
    cot = r.json()["id"]
    if aprobada:
        await _aprobar(cliente, "cotizaciones", cot)
    return cot


async def _orden(cliente, aprobada: bool = True) -> str:
    cot = await _cotizacion(cliente)
    r = await cliente.post(
        f"{BASE}/ordenes-compra",
        json={
            "cotizacion_id": cot,
            "estado_id": await _estado(cliente, CODIGO_PENDIENTE),
        },
    )
    assert r.status_code == 201, r.text
    orden = r.json()["id"]
    if aprobada:
        await _aprobar(cliente, "ordenes-compra", orden)
    return orden


async def _guia(cliente) -> str:
    orden = await _orden(cliente)
    r = await cliente.post(
        f"{BASE}/guias-remision",
        json={
            "orden_compra_id": orden,
            "estado_id": await _estado(cliente, CODIGO_PENDIENTE),
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ===================== Los estados canónicos existen =====================


@pytest.mark.parametrize(
    "codigo",
    [CODIGO_PENDIENTE, CODIGO_APROBADO, CODIGO_RECEPCIONADO, CODIGO_ATENDIDO],
)
async def test_los_estados_de_la_cadena_vienen_sembrados(cliente, codigo):
    """Sin ellos la cadena no puede operar, así que los pone la migración."""
    assert await _estado(cliente, codigo)


# ===================== Cada eslabón exige el anterior aprobado =====================


async def test_no_hay_pedido_sin_requerimiento_aprobado(cliente):
    req = await _requerimiento(cliente, aprobado=False)

    r = await cliente.post(
        f"{BASE}/pedidos",
        json={
            "requerimiento_id": req,
            "estado_id": await _estado(cliente, CODIGO_PENDIENTE),
        },
    )

    assert r.status_code == 409
    assert "no está aprobado" in r.json()["detail"]


async def test_con_el_requerimiento_aprobado_el_pedido_nace(cliente):
    req = await _requerimiento(cliente, aprobado=True)

    r = await cliente.post(
        f"{BASE}/pedidos",
        json={
            "requerimiento_id": req,
            "estado_id": await _estado(cliente, CODIGO_PENDIENTE),
        },
    )

    assert r.status_code == 201, r.text


async def test_no_hay_cotizacion_sin_pedido_aprobado(cliente):
    pedido = await _pedido(cliente, aprobado=False)

    r = await cliente.post(
        f"{BASE}/cotizaciones",
        json={
            "pedido_id": pedido,
            "proveedor_id": await _proveedor(cliente),
            "estado_id": await _estado(cliente, CODIGO_PENDIENTE),
        },
    )

    assert r.status_code == 409


async def test_no_hay_orden_sin_cotizacion_aprobada(cliente):
    cot = await _cotizacion(cliente, aprobada=False)

    r = await cliente.post(
        f"{BASE}/ordenes-compra",
        json={
            "cotizacion_id": cot,
            "estado_id": await _estado(cliente, CODIGO_PENDIENTE),
        },
    )

    assert r.status_code == 409


async def test_no_hay_guia_sin_orden_aprobada(cliente):
    orden = await _orden(cliente, aprobada=False)

    r = await cliente.post(
        f"{BASE}/guias-remision",
        json={
            "orden_compra_id": orden,
            "estado_id": await _estado(cliente, CODIGO_PENDIENTE),
        },
    )

    assert r.status_code == 409


async def test_varias_cotizaciones_por_pedido(cliente):
    """Comparar ofertas es el sentido del paso: no puede haber una sola."""
    pedido = await _pedido(cliente)
    pendiente = await _estado(cliente, CODIGO_PENDIENTE)

    for i, ruc in enumerate(("20552103816", "20100070970")):
        r = await cliente.post(
            f"{BASE}/cotizaciones",
            json={
                "pedido_id": pedido,
                "proveedor_id": await _proveedor(cliente, ruc),
                "estado_id": pendiente,
            },
        )
        assert r.status_code == 201, f"cotización {i}: {r.text}"


# ===================== Reapuntar el padre revalida =====================


async def test_no_se_puede_reapuntar_a_un_padre_sin_aprobar(cliente):
    """El hueco evidente si solo se validara el alta."""
    pedido = await _pedido(cliente, aprobado=False)
    otro_req = await _requerimiento(cliente, aprobado=False)

    r = await cliente.patch(
        f"{BASE}/pedidos/{pedido}", json={"requerimiento_id": otro_req}
    )

    assert r.status_code == 409


async def test_editar_otro_campo_no_revalida(cliente):
    """Cambiar la fecha de un pedido no tiene por qué mirar al padre."""
    pedido = await _pedido(cliente, aprobado=False)

    r = await cliente.patch(f"{BASE}/pedidos/{pedido}", json={"fecha": "2026-08-20"})

    assert r.status_code == 200, r.text


# ===================== La recepción cierra la cadena =====================


async def test_recepcionar_la_guia_cierra_toda_la_cadena(cliente):
    """El caso que da sentido a la recepción."""
    guia = await _guia(cliente)
    almacen = await _almacen(cliente)

    r = await cliente.post(
        f"{BASE}/recepciones",
        json={"guia_remision_id": guia, "almacen_id": almacen},
    )

    assert r.status_code == 201, r.text
    recepcion = r.json()
    assert await _codigo_de(cliente, "recepciones", recepcion["id"]) == (
        CODIGO_RECEPCIONADO
    )
    assert await _codigo_de(cliente, "guias-remision", guia) == CODIGO_RECEPCIONADO

    # Y todo lo anterior queda atendido: lo que pedía ya llegó.
    orden = recepcion["orden_compra_id"]
    assert orden is not None, "la recepción hereda la orden desde la guía"
    assert await _codigo_de(cliente, "ordenes-compra", orden) == CODIGO_ATENDIDO

    o = (await cliente.get(f"{BASE}/ordenes-compra/{orden}")).json()
    c = (await cliente.get(f"{BASE}/cotizaciones/{o['cotizacion_id']}")).json()
    assert await _codigo_de(cliente, "cotizaciones", c["id"]) == CODIGO_ATENDIDO
    assert await _codigo_de(cliente, "pedidos", c["pedido_id"]) == CODIGO_ATENDIDO

    p = (await cliente.get(f"{BASE}/pedidos/{c['pedido_id']}")).json()
    assert await _codigo_de(cliente, "requerimientos", p["requerimiento_id"]) == (
        CODIGO_ATENDIDO
    )


async def test_la_misma_guia_no_se_recepciona_dos_veces(cliente):
    guia = await _guia(cliente)
    almacen = await _almacen(cliente)
    alta = {"guia_remision_id": guia, "almacen_id": almacen}

    assert (await cliente.post(f"{BASE}/recepciones", json=alta)).status_code == 201

    r = await cliente.post(f"{BASE}/recepciones", json=alta)

    assert r.status_code == 409
    assert "ya está recepcionada" in r.json()["detail"]


async def test_una_recepcion_sin_guia_ni_orden_es_400(cliente):
    """Sin una de las dos no se sabe qué se está recibiendo."""
    almacen = await _almacen(cliente)

    r = await cliente.post(f"{BASE}/recepciones", json={"almacen_id": almacen})

    assert r.status_code == 400


async def test_la_guia_y_la_orden_tienen_que_coincidir(cliente):
    """Si no, se cerraría la cadena de una orden ajena a lo que llegó."""
    guia = await _guia(cliente)
    otra_orden = await _orden(cliente)
    almacen = await _almacen(cliente)

    r = await cliente.post(
        f"{BASE}/recepciones",
        json={
            "guia_remision_id": guia,
            "orden_compra_id": otra_orden,
            "almacen_id": almacen,
        },
    )

    assert r.status_code == 409


async def test_se_puede_recepcionar_contra_la_orden_sin_guia(cliente):
    """El proveedor que entrega sin guía previa."""
    orden = await _orden(cliente)
    almacen = await _almacen(cliente)

    r = await cliente.post(
        f"{BASE}/recepciones",
        json={"orden_compra_id": orden, "almacen_id": almacen},
    )

    assert r.status_code == 201, r.text
    assert await _codigo_de(cliente, "ordenes-compra", orden) == CODIGO_ATENDIDO


async def test_la_recepcion_se_filtra_por_guia(cliente):
    guia = await _guia(cliente)
    almacen = await _almacen(cliente)
    recepcion = (
        await cliente.post(
            f"{BASE}/recepciones",
            json={"guia_remision_id": guia, "almacen_id": almacen},
        )
    ).json()["id"]

    r = await cliente.get(f"{BASE}/recepciones", params={"guia_remision_id": guia})

    assert [x["id"] for x in r.json()["items"]] == [recepcion]
