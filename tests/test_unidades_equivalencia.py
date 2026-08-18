"""La unidad de medida y su equivalencia se administran como una sola cosa.

`factor_conversion` vive en `tabla_equivalencia` por el `UNIQUE` que impide dos
factores por unidad, pero para quien usa el sistema es un atributo de la unidad:
sin él, `conversion.factor_de` corta con 400 al usarla en un movimiento. Por eso
el alta las escribe juntas, en la misma transacción.
"""

from __future__ import annotations

BASE = "/api/v1"


async def _crear(cliente, **campos):
    datos = {"descripcion": "Unidad", "codigo": "UND"} | campos
    return await cliente.post(f"{BASE}/unidades-medida", json=datos)


# ===================== Alta =====================


async def test_el_alta_registra_la_equivalencia(cliente):
    r = await _crear(cliente, descripcion="Caja de 12", codigo="CAJA12", factor_conversion=12)

    assert r.status_code == 201
    assert r.json()["factor_conversion"] == 12

    unidad_id = r.json()["id"]
    equivalencias = (
        await cliente.get(f"{BASE}/tablas-equivalencia", params={"unidad_medida_id": unidad_id})
    ).json()["items"]
    assert len(equivalencias) == 1
    assert equivalencias[0]["factor_conversion"] == 12


async def test_el_factor_por_defecto_es_uno(cliente):
    """La unidad base es el caso común: se crea sin pensar en el factor."""
    r = await _crear(cliente, descripcion="Unidad", codigo="UND")

    assert r.status_code == 201
    assert r.json()["factor_conversion"] == 1


async def test_ninguna_unidad_nace_sin_equivalencia(cliente):
    """Es la razón de ser del campo: sin fila, la unidad revienta al usarse."""
    await _crear(cliente, descripcion="Unidad", codigo="UND")
    await _crear(cliente, descripcion="Docena", codigo="DOC", factor_conversion=12)

    unidades = (await cliente.get(f"{BASE}/unidades-medida")).json()["items"]
    assert len(unidades) == 2
    assert all(u["factor_conversion"] is not None for u in unidades)


async def test_un_factor_menor_a_uno_se_rechaza(cliente):
    """Cero anularía cualquier cantidad al convertir; negativo no significa nada."""
    assert (await _crear(cliente, factor_conversion=0)).status_code == 422
    assert (await _crear(cliente, codigo="X", factor_conversion=-3)).status_code == 422


async def test_el_alta_es_atomica(cliente):
    """Si la unidad se rechaza por duplicada, no queda equivalencia suelta."""
    await _crear(cliente, descripcion="Caja", codigo="CAJ", factor_conversion=6)
    antes = (await cliente.get(f"{BASE}/tablas-equivalencia")).json()["total"]

    repetida = await _crear(cliente, descripcion="Caja", codigo="CAJ", factor_conversion=6)

    assert repetida.status_code == 409
    despues = (await cliente.get(f"{BASE}/tablas-equivalencia")).json()["total"]
    assert despues == antes


# ===================== Edición =====================


async def test_editar_el_factor_actualiza_la_equivalencia(cliente):
    unidad = (await _crear(cliente, codigo="CAJA6", factor_conversion=6)).json()

    r = await cliente.patch(
        f"{BASE}/unidades-medida/{unidad['id']}", json={"factor_conversion": 24}
    )

    assert r.status_code == 200
    assert r.json()["factor_conversion"] == 24

    equivalencias = (
        await cliente.get(
            f"{BASE}/tablas-equivalencia", params={"unidad_medida_id": unidad["id"]}
        )
    ).json()["items"]
    # Actualiza la fila, no agrega otra: el UNIQUE por unidad lo impediría.
    assert len(equivalencias) == 1
    assert equivalencias[0]["factor_conversion"] == 24


async def test_editar_solo_la_descripcion_no_toca_el_factor(cliente):
    unidad = (await _crear(cliente, codigo="CAJA6", factor_conversion=6)).json()

    r = await cliente.patch(
        f"{BASE}/unidades-medida/{unidad['id']}", json={"descripcion": "Caja de seis"}
    )

    assert r.status_code == 200
    assert r.json()["descripcion"] == "Caja de seis"
    assert r.json()["factor_conversion"] == 6


async def test_editar_completa_la_equivalencia_que_falta(cliente):
    """Las unidades anteriores a este campo no tienen fila; editarlas es la vía
    para completarlas, así que el guardado es un upsert y no un update."""
    unidad = (await _crear(cliente, codigo="VIEJA")).json()
    equivalencia = (
        await cliente.get(
            f"{BASE}/tablas-equivalencia", params={"unidad_medida_id": unidad["id"]}
        )
    ).json()["items"][0]
    await cliente.delete(f"{BASE}/tablas-equivalencia/{equivalencia['id']}")

    r = await cliente.patch(
        f"{BASE}/unidades-medida/{unidad['id']}", json={"factor_conversion": 10}
    )

    assert r.status_code == 200
    assert r.json()["factor_conversion"] == 10


async def test_mandar_el_factor_en_null_se_rechaza(cliente):
    """Omitirlo es válido en un PATCH; mandarlo vacío es borrar el dato."""
    unidad = (await _crear(cliente, codigo="CAJA6", factor_conversion=6)).json()

    r = await cliente.patch(
        f"{BASE}/unidades-medida/{unidad['id']}", json={"factor_conversion": None}
    )

    assert r.status_code == 422
