"""El detalle de la recepción, cuadrado contra lo que la guía declaró.

La guía dice qué trae el proveedor; la recepción, qué se aceptó de eso. Que lo
ingresado no supere lo declarado es lo que impide que entre stock sin respaldo
documental, y como la guía puede venir en cajas y la recepción en unidades
sueltas, la comparación se hace en unidad mínima.

Los helpers de la cadena se reutilizan de `test_cadena_compras`: montar un
requerimiento aprobado, su pedido, su cotización, su orden y su guía es
exactamente lo mismo acá, y duplicarlo sería tener dos versiones de la cadena
que se pueden desincronizar.
"""

from __future__ import annotations

import pytest

from tests.conftest import producto_valido
from tests.test_cadena_compras import BASE, _almacen, _guia, _orden


async def _producto(cliente, catalogo, sku="ARR-EXT-5K") -> str:
    r = await cliente.post(f"{BASE}/productos", json=producto_valido(catalogo, sku))
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _unidad(cliente, descripcion="Unidad", codigo="UND", factor=1) -> str:
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


async def _recepcion_de_guia(cliente, guia) -> str:
    r = await cliente.post(
        f"{BASE}/recepciones",
        json={"guia_remision_id": guia, "almacen_id": await _almacen(cliente)},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _guia_con_linea(cliente, catalogo, cantidad=50, unidad=None):
    """Guía que declara `cantidad` de un producto, con su recepción abierta.

    Devuelve (recepcion, producto, unidad).
    """
    guia = await _guia(cliente)
    producto = await _producto(cliente, catalogo)
    unidad = unidad or await _unidad(cliente)
    r = await cliente.post(
        f"{BASE}/guias-remision-detalle",
        json={
            "guia_remision_id": guia,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "cantidad": cantidad,
        },
    )
    assert r.status_code == 201, r.text
    return await _recepcion_de_guia(cliente, guia), producto, unidad


# ===================== Lo recibido cuadra con lo declarado =====================


async def test_recibir_lo_que_la_guia_declara(cliente, catalogo):
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)

    r = await cliente.post(
        f"{BASE}/recepciones-detalle",
        json={
            "recepcion_id": recepcion,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "cantidad_esperada": 50,
            "cantidad_ingresada": 50,
        },
    )

    assert r.status_code == 201, r.text
    assert r.json()["cantidad_ingresada"] == 50


async def test_no_se_puede_recibir_mas_de_lo_declarado(cliente, catalogo):
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)

    r = await cliente.post(
        f"{BASE}/recepciones-detalle",
        json={
            "recepcion_id": recepcion,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "cantidad_esperada": 50,
            "cantidad_ingresada": 51,
        },
    )

    assert r.status_code == 409
    assert "51" in r.json()["detail"] and "50" in r.json()["detail"]


async def test_recibir_de_menos_es_valido(cliente, catalogo):
    """El proveedor entregó parcialmente: se deja constancia, no se bloquea."""
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)

    r = await cliente.post(
        f"{BASE}/recepciones-detalle",
        json={
            "recepcion_id": recepcion,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            "cantidad_esperada": 50,
            "cantidad_ingresada": 30,
            "cantidad_devuelta": 20,
        },
    )

    assert r.status_code == 201, r.text


async def test_editar_la_linea_tambien_se_valida(cliente, catalogo):
    """Si no, bastaría con crear en cero y subir después."""
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    linea = (
        await cliente.post(
            f"{BASE}/recepciones-detalle",
            json={
                "recepcion_id": recepcion,
                "producto_id": producto,
                "unidad_medida_id": unidad,
                "cantidad_ingresada": 50,
            },
        )
    ).json()["id"]

    assert (
        await cliente.patch(
            f"{BASE}/recepciones-detalle/{linea}", json={"cantidad_ingresada": 51}
        )
    ).status_code == 409
    # Bajarla sí, y la propia línea no se cuenta dos veces.
    assert (
        await cliente.patch(
            f"{BASE}/recepciones-detalle/{linea}", json={"cantidad_ingresada": 20}
        )
    ).status_code == 200


async def test_recibir_algo_que_la_guia_no_declara_es_400(cliente, catalogo):
    recepcion = await _recepcion_de_guia(cliente, await _guia(cliente))

    r = await cliente.post(
        f"{BASE}/recepciones-detalle",
        json={
            "recepcion_id": recepcion,
            "producto_id": await _producto(cliente, catalogo),
            "unidad_medida_id": await _unidad(cliente),
            "cantidad_ingresada": 5,
        },
    )

    assert r.status_code == 400
    assert "no declara" in r.json()["detail"]


async def test_el_producto_no_se_repite_en_la_misma_recepcion(cliente, catalogo):
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    linea = {
        "recepcion_id": recepcion,
        "producto_id": producto,
        "unidad_medida_id": unidad,
        "cantidad_ingresada": 10,
    }

    assert (
        await cliente.post(f"{BASE}/recepciones-detalle", json=linea)
    ).status_code == 201

    r = await cliente.post(f"{BASE}/recepciones-detalle", json=linea)

    assert r.status_code == 409


# ============ Guía en paquetes, recepción en unidad suelta ============


async def test_cuatro_cajas_de_doce_se_reciben_como_48_unidades(cliente, catalogo):
    caja = await _unidad(cliente, "Caja x12", "CAJA12", factor=12)
    recepcion, producto, _ = await _guia_con_linea(cliente, catalogo, 4, unidad=caja)
    suelta = await _unidad(cliente, "Unidad suelta", "UND2", factor=1)

    r = await cliente.post(
        f"{BASE}/recepciones-detalle",
        json={
            "recepcion_id": recepcion,
            "producto_id": producto,
            "unidad_medida_id": suelta,
            "cantidad_ingresada": 48,
        },
    )
    assert r.status_code == 201, "48 sueltas caben justo en 4 cajas de 12"

    # La 49 ya no. Sin convertir, comparar 49 contra 4 habría cortado antes y
    # comparar 48 contra 4 lo habría dado por malo: los dos casos fallan.
    r = await cliente.patch(
        f"{BASE}/recepciones-detalle/{r.json()['id']}",
        json={"cantidad_ingresada": 49},
    )
    assert r.status_code == 409


async def test_sin_equivalencia_registrada_es_400(cliente, catalogo):
    recepcion, producto, _ = await _guia_con_linea(cliente, catalogo, 50)
    # El alta de unidad ya exige el factor, así que para quedarse sin él hay
    # que dar de baja la equivalencia después.
    huerfana = await _unidad(cliente, "Sin factor", "NOFAC")
    equivalencia = (
        await cliente.get(
            f"{BASE}/tablas-equivalencia", params={"unidad_medida_id": huerfana}
        )
    ).json()["items"][0]["id"]
    await cliente.delete(f"{BASE}/tablas-equivalencia/{equivalencia}")

    r = await cliente.post(
        f"{BASE}/recepciones-detalle",
        json={
            "recepcion_id": recepcion,
            "producto_id": producto,
            "unidad_medida_id": huerfana,
            "cantidad_ingresada": 1,
        },
    )

    assert r.status_code == 400
    assert "NOFAC" in r.json()["detail"]


# ===================== Recepción sin guía =====================


async def test_sin_guia_no_hay_contra_que_cuadrar(cliente, catalogo):
    """Contra orden directa se acepta lo que entre: no hay guía que lo limite."""
    orden = await _orden(cliente)
    recepcion = (
        await cliente.post(
            f"{BASE}/recepciones",
            json={"orden_compra_id": orden, "almacen_id": await _almacen(cliente)},
        )
    ).json()["id"]

    r = await cliente.post(
        f"{BASE}/recepciones-detalle",
        json={
            "recepcion_id": recepcion,
            "producto_id": await _producto(cliente, catalogo),
            "unidad_medida_id": await _unidad(cliente),
            "cantidad_ingresada": 999,
        },
    )

    assert r.status_code == 201, r.text


# ===================== Integridad =====================


async def test_filtrar_lineas_por_recepcion(cliente, catalogo):
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)
    linea = (
        await cliente.post(
            f"{BASE}/recepciones-detalle",
            json={
                "recepcion_id": recepcion,
                "producto_id": producto,
                "unidad_medida_id": unidad,
                "cantidad_ingresada": 7,
            },
        )
    ).json()["id"]

    r = await cliente.get(
        f"{BASE}/recepciones-detalle", params={"recepcion_id": recepcion}
    )

    assert [x["id"] for x in r.json()["items"]] == [linea]


@pytest.mark.parametrize(
    "campo", ["cantidad_esperada", "cantidad_ingresada", "cantidad_devuelta"]
)
async def test_cantidad_negativa_es_422(cliente, catalogo, campo):
    recepcion, producto, unidad = await _guia_con_linea(cliente, catalogo, 50)

    r = await cliente.post(
        f"{BASE}/recepciones-detalle",
        json={
            "recepcion_id": recepcion,
            "producto_id": producto,
            "unidad_medida_id": unidad,
            campo: -1,
        },
    )

    assert r.status_code == 422


async def test_la_recepcion_inexistente_es_400(cliente, catalogo):
    import uuid

    r = await cliente.post(
        f"{BASE}/recepciones-detalle",
        json={
            "recepcion_id": str(uuid.uuid4()),
            "producto_id": await _producto(cliente, catalogo),
            "unidad_medida_id": await _unidad(cliente),
            "cantidad_ingresada": 1,
        },
    )

    assert r.status_code == 400
