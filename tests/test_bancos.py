"""Bancos, tipos de cuenta y cuentas bancarias.

Una cuenta cruza tres referencias: banco, empresa y tipo de cuenta. El número
es único dentro de su banco, no en toda la tabla: dos bancos distintos pueden
usar la misma numeración.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

BASE = "/api/v1"

BANCO = {
    "razon_social": "BANCO DE CREDITO DEL PERU",
    "ruc": "20100047218",
    "codigo": "BCP",
}


async def _crear_banco(cliente, **extra) -> str:
    r = await cliente.post(f"{BASE}/bancos", json={**BANCO, **extra})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _crear_tipo(cliente, descripcion="Corriente", codigo="CTE") -> str:
    r = await cliente.post(
        f"{BASE}/tipos-cuenta", json={"descripcion": descripcion, "codigo": codigo}
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _crear_empresa(cliente, ruc="20552103816") -> str:
    r = await cliente.post(
        f"{BASE}/empresas",
        json={
            "razon_social": f"EMPRESA {ruc}",
            "ruc": ruc,
            "ubigeo_sunat": "150101",
            "estado": "ACTIVO",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ===================== Bancos =====================


async def test_los_opcionales_no_hay_que_enviarlos(cliente):
    """Antes `direccion` y `telefono` eran obligatorios-que-admiten-null."""
    r = await cliente.post(
        f"{BASE}/bancos",
        json={"razon_social": "BANCO SIN DATOS", "ruc": "20100047218"},
    )

    assert r.status_code == 201, r.text
    assert r.json()["direccion"] is None
    assert r.json()["telefono"] is None


@pytest.mark.parametrize("ruc", ["123", "2010004721A", "abcdefghijk"])
async def test_ruc_de_banco_mal_formado_es_422(cliente, ruc):
    r = await cliente.post(f"{BASE}/bancos", json={**BANCO, "ruc": ruc})
    assert r.status_code == 422


async def test_ruc_de_banco_repetido_es_409(cliente):
    await _crear_banco(cliente)

    r = await cliente.post(
        f"{BASE}/bancos", json={**BANCO, "razon_social": "OTRO", "codigo": "OTR"}
    )

    assert r.status_code == 409


async def test_dos_bancos_sin_codigo_no_chocan(cliente):
    """El índice de código es parcial: los nulos no compiten entre sí."""
    await cliente.post(
        f"{BASE}/bancos", json={"razon_social": "BANCO A", "ruc": "20100047218"}
    )

    r = await cliente.post(
        f"{BASE}/bancos", json={"razon_social": "BANCO B", "ruc": "20382036655"}
    )

    assert r.status_code == 201


async def test_patch_parcial_de_banco(cliente):
    banco = await _crear_banco(cliente)

    r = await cliente.patch(f"{BASE}/bancos/{banco}", json={"telefono": "013115000"})

    assert r.status_code == 200, r.text
    assert r.json()["telefono"] == "013115000"
    assert r.json()["razon_social"] == BANCO["razon_social"]


# ===================== Cuentas =====================


async def test_crear_una_cuenta(cliente):
    banco = await _crear_banco(cliente)
    tipo = await _crear_tipo(cliente)
    empresa = await _crear_empresa(cliente)

    r = await cliente.post(
        f"{BASE}/cuentas",
        json={
            "numero_cuenta": "1912345678094",
            "banco_id": banco,
            "empresa_id": empresa,
            "tipo_cuenta_id": tipo,
            "moneda": "PEN",
        },
    )

    assert r.status_code == 201, r.text
    assert r.json()["moneda"] == "PEN"


@pytest.mark.parametrize("moneda", ["soles", "S/", "pen", "EUR", ""])
async def test_moneda_no_admitida_es_422(cliente, moneda):
    banco = await _crear_banco(cliente)
    tipo = await _crear_tipo(cliente)
    empresa = await _crear_empresa(cliente)

    r = await cliente.post(
        f"{BASE}/cuentas",
        json={
            "numero_cuenta": "1912345678094",
            "banco_id": banco,
            "empresa_id": empresa,
            "tipo_cuenta_id": tipo,
            "moneda": moneda,
        },
    )

    assert r.status_code == 422


async def test_el_numero_es_unico_dentro_del_banco_no_fuera(cliente):
    banco_a = await _crear_banco(cliente)
    banco_b = await _crear_banco(
        cliente, razon_social="BANCO B", ruc="20382036655", codigo="BBV"
    )
    tipo = await _crear_tipo(cliente)
    empresa = await _crear_empresa(cliente)
    numero = "1912345678094"

    base = {
        "numero_cuenta": numero,
        "empresa_id": empresa,
        "tipo_cuenta_id": tipo,
        "moneda": "PEN",
    }
    assert (
        await cliente.post(f"{BASE}/cuentas", json={**base, "banco_id": banco_a})
    ).status_code == 201

    # Mismo número en otro banco: válido.
    assert (
        await cliente.post(f"{BASE}/cuentas", json={**base, "banco_id": banco_b})
    ).status_code == 201

    # Repetido en el mismo banco: choca.
    assert (
        await cliente.post(f"{BASE}/cuentas", json={**base, "banco_id": banco_a})
    ).status_code == 409


async def test_cuenta_con_referencia_inexistente_es_400(cliente):
    tipo = await _crear_tipo(cliente)
    empresa = await _crear_empresa(cliente)

    r = await cliente.post(
        f"{BASE}/cuentas",
        json={
            "numero_cuenta": "1912345678094",
            "banco_id": str(uuid4()),
            "empresa_id": empresa,
            "tipo_cuenta_id": tipo,
            "moneda": "PEN",
        },
    )

    assert r.status_code == 400


async def test_filtrar_cuentas_por_empresa_y_por_banco(cliente):
    banco_a = await _crear_banco(cliente)
    banco_b = await _crear_banco(
        cliente, razon_social="BANCO B", ruc="20382036655", codigo="BBV"
    )
    tipo = await _crear_tipo(cliente)
    empresa_1 = await _crear_empresa(cliente, "20552103816")
    empresa_2 = await _crear_empresa(cliente, "20100047218")

    async def crear(banco, empresa, numero):
        r = await cliente.post(
            f"{BASE}/cuentas",
            json={
                "numero_cuenta": numero,
                "banco_id": banco,
                "empresa_id": empresa,
                "tipo_cuenta_id": tipo,
                "moneda": "USD",
            },
        )
        assert r.status_code == 201, r.text
        return r.json()["id"]

    de_empresa_1 = await crear(banco_a, empresa_1, "111")
    await crear(banco_b, empresa_2, "222")

    por_empresa = await cliente.get(f"{BASE}/cuentas", params={"empresa_id": empresa_1})
    assert [c["id"] for c in por_empresa.json()["items"]] == [de_empresa_1]

    por_banco = await cliente.get(f"{BASE}/cuentas", params={"banco_id": banco_a})
    assert [c["id"] for c in por_banco.json()["items"]] == [de_empresa_1]
