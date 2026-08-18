"""Zonas, sedes y markets.

La jerarquía es zona → sede → market. El nombre es único dentro de su padre y
el código lo es en toda la tabla, igual que en el catálogo de productos.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

BASE = "/api/v1"


async def _crear_zona(cliente, nombre="Norte", codigo="NOR") -> str:
    r = await cliente.post(f"{BASE}/zonas", json={"nombre": nombre, "codigo": codigo})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _crear_sede(cliente, zona_id, nombre="Sede Lima", codigo="LIM") -> str:
    r = await cliente.post(
        f"{BASE}/sedes",
        json={"zona_id": zona_id, "nombre": nombre, "codigo": codigo},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ===================== CRUD básico =====================


async def test_ciclo_completo_de_la_jerarquia(cliente):
    zona = await _crear_zona(cliente)
    sede = await _crear_sede(cliente, zona)

    r = await cliente.post(
        f"{BASE}/markets", json={"sede_id": sede, "nombre": "Market 1", "codigo": "MK1"}
    )

    assert r.status_code == 201
    assert r.json()["sede_id"] == sede
    assert r.json()["is_active"] is True


async def test_baja_logica_lo_saca_del_listado(cliente):
    zona = await _crear_zona(cliente)

    await cliente.delete(f"{BASE}/zonas/{zona}")

    activas = (await cliente.get(f"{BASE}/zonas")).json()
    todas = (await cliente.get(f"{BASE}/zonas", params={"solo_activos": False})).json()
    assert [z["id"] for z in activas["items"]] == []
    assert [z["id"] for z in todas["items"]] == [zona]


# ===================== El PATCH parcial =====================


async def test_patch_parcial_no_exige_los_demas_campos(cliente):
    """Con los `*Update` mal declarados esto daba 422 por no mandar `codigo`."""
    zona = await _crear_zona(cliente, nombre="Norte", codigo="NOR")

    r = await cliente.patch(f"{BASE}/zonas/{zona}", json={"nombre": "Nor-Este"})

    assert r.status_code == 200, r.text
    assert r.json()["nombre"] == "Nor-Este"
    assert r.json()["codigo"] == "NOR", "lo no enviado no debe cambiar"


async def test_patch_con_null_en_campo_obligatorio_es_422(cliente):
    """`codigo` es NOT NULL: mandar null debe ser un 422, no un 500."""
    zona = await _crear_zona(cliente)

    r = await cliente.patch(f"{BASE}/zonas/{zona}", json={"codigo": None})

    assert r.status_code == 422


async def test_mover_una_sede_de_zona(cliente):
    zona_a = await _crear_zona(cliente, "Norte", "NOR")
    zona_b = await _crear_zona(cliente, "Sur", "SUR")
    sede = await _crear_sede(cliente, zona_a)

    r = await cliente.patch(f"{BASE}/sedes/{sede}", json={"zona_id": zona_b})

    assert r.status_code == 200
    assert r.json()["zona_id"] == zona_b


# ===================== Unicidad =====================


async def test_codigo_de_zona_repetido_es_409(cliente):
    await _crear_zona(cliente, "Norte", "NOR")

    r = await cliente.post(f"{BASE}/zonas", json={"nombre": "Otra", "codigo": "NOR"})

    assert r.status_code == 409


async def test_la_unicidad_ignora_mayusculas_y_espacios(cliente):
    await _crear_zona(cliente, "Norte", "NOR")

    r = await cliente.post(f"{BASE}/zonas", json={"nombre": "Otra", "codigo": " nor "})

    assert r.status_code == 409


async def test_el_nombre_de_sede_solo_es_unico_dentro_de_su_zona(cliente):
    zona_a = await _crear_zona(cliente, "Norte", "NOR")
    zona_b = await _crear_zona(cliente, "Sur", "SUR")
    await _crear_sede(cliente, zona_a, "Central", "CEN")

    # Mismo nombre en otra zona: válido. El código sí es global, va otro.
    r = await cliente.post(
        f"{BASE}/sedes",
        json={"zona_id": zona_b, "nombre": "Central", "codigo": "CE2"},
    )
    assert r.status_code == 201

    # Mismo nombre en la misma zona: choca.
    r = await cliente.post(
        f"{BASE}/sedes",
        json={"zona_id": zona_a, "nombre": "Central", "codigo": "CE3"},
    )
    assert r.status_code == 409


# ===================== Validación y referencias =====================


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"nombre": "", "codigo": "NOR"},
        {"nombre": "x" * 51, "codigo": "NOR"},
        {"nombre": "Norte", "codigo": ""},
        {"nombre": "Norte", "codigo": "x" * 11},
        {"nombre": "Norte"},
    ],
)
async def test_alta_invalida_es_422(cliente, cuerpo):
    r = await cliente.post(f"{BASE}/zonas", json=cuerpo)
    assert r.status_code == 422


async def test_sede_con_zona_inexistente_es_400(cliente):
    r = await cliente.post(
        f"{BASE}/sedes",
        json={"zona_id": str(uuid4()), "nombre": "Huérfana", "codigo": "HUE"},
    )
    assert r.status_code == 400


# ===================== Filtros =====================


async def test_filtrar_sedes_por_zona(cliente):
    zona_a = await _crear_zona(cliente, "Norte", "NOR")
    zona_b = await _crear_zona(cliente, "Sur", "SUR")
    sede_a = await _crear_sede(cliente, zona_a, "Uno", "UNO")
    await _crear_sede(cliente, zona_b, "Dos", "DOS")

    r = await cliente.get(f"{BASE}/sedes", params={"zona_id": zona_a})

    assert [s["id"] for s in r.json()["items"]] == [sede_a]
