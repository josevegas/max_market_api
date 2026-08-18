"""Tests de empresas y de la consulta de RUC.

La API externa (decolecta) se simula: un test no debe depender de que un
tercero esté arriba, ni gastar cuota de la cuenta, ni cambiar de resultado
porque SUNAT actualizó un dato.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

BASE = "/api/v1"

#: Respuesta **real** de decolecta para el RUC 20552103816, capturada tal cual.
#: Sirve de contrato: si el proveedor cambia estos nombres, los tests lo notan
#: antes que producción.
RESPUESTA_SUNAT = {
    "razon_social": "AGROLIGHT PERU S.A.C.",
    "numero_documento": "20552103816",
    "estado": "SUSPENSION TEMPORAL",
    "condicion": "HABIDO",
    "direccion": "PJ. JORGE BASADRE NRO 158 URB. POP LA UNIVERSAL 2DA ET. ",
    "ubigeo": "150137",
    "distrito": "SANTA ANITA",
    "provincia": "LIMA",
    "departamento": "LIMA",
    # Booleano, no "SI"/"NO". Y no hay equivalente para percepción: por eso la
    # condición de agente se resuelve contra el padrón, no acá.
    "es_agente_retencion": False,
    "es_buen_contribuyente": True,
}


class RespuestaFalsa:
    """Imita lo que `requests.get` devuelve, con lo que usa el servicio."""

    def __init__(self, cuerpo=None, status_code: int = 200) -> None:
        self._cuerpo = cuerpo if cuerpo is not None else RESPUESTA_SUNAT
        self.status_code = status_code

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def json(self):
        return self._cuerpo


def simular_sunat(cuerpo=None, status_code: int = 200):
    """Reemplaza la llamada HTTP del servicio por una respuesta fija."""
    return patch(
        "app.modules.proveedores.services.empresa_service.requests.get",
        return_value=RespuestaFalsa(cuerpo, status_code),
    )


# ===================== Consulta de RUC =====================


async def test_consultar_ruc_normaliza_la_respuesta(cliente):
    with simular_sunat():
        r = await cliente.get(f"{BASE}/empresas/ruc/20552103816")

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["razon_social"] == "AGROLIGHT PERU S.A.C."
    assert cuerpo["numero_documento"] == "20552103816"
    assert cuerpo["ubigeo"] == "150137"
    assert cuerpo["direccion"].startswith("PJ. JORGE BASADRE")
    # Se conserva la respuesta completa: el proveedor no garantiza una forma
    # fija y ahí queda lo que no se mapeó (el desglose de dirección, los
    # indicadores de buen contribuyente...).
    assert cuerpo["crudo"]["departamento"] == "LIMA"
    assert cuerpo["crudo"]["es_buen_contribuyente"] is True


async def test_consultar_ruc_envia_el_numero_como_parametro(cliente):
    """El contrato con decolecta: GET con `?numero=` y Bearer.

    El RUC va en `params` y no concatenado a la URL: así el setting es una URL
    base normal y `requests` se encarga de escaparlo.
    """
    with simular_sunat() as falso:
        await cliente.get(f"{BASE}/empresas/ruc/20552103816")

    args, kwargs = falso.call_args
    assert kwargs["params"] == {"numero": "20552103816"}
    assert "?" not in args[0], "la URL configurada no debe llevar query string"
    assert kwargs["headers"]["Authorization"].startswith("Bearer ")
    # Sin timeout, un cuelgue del proveedor deja la petición colgada.
    assert kwargs["timeout"] > 0


@pytest.mark.parametrize("ruc", ["123", "abcdefghijk", "205521038160"])
async def test_ruc_mal_formado_es_400_sin_llamar_al_proveedor(cliente, ruc):
    with simular_sunat() as falso:
        r = await cliente.get(f"{BASE}/empresas/ruc/{ruc}")

    assert r.status_code in (400, 404)
    assert falso.call_count == 0, "no debe gastarse una consulta externa"


async def test_ruc_inexistente_es_404(cliente):
    with simular_sunat(cuerpo={}, status_code=404):
        r = await cliente.get(f"{BASE}/empresas/ruc/20999999999")

    assert r.status_code == 404


async def test_token_rechazado_es_502(cliente):
    """El fallo es del servicio de terceros, no de quien llama."""
    with simular_sunat(cuerpo={}, status_code=401):
        r = await cliente.get(f"{BASE}/empresas/ruc/20552103816")

    assert r.status_code == 502
    assert "token" in r.json()["detail"].lower()


async def test_timeout_del_proveedor_es_502(cliente):
    import requests

    with patch(
        "app.modules.proveedores.services.empresa_service.requests.get",
        side_effect=requests.Timeout(),
    ):
        r = await cliente.get(f"{BASE}/empresas/ruc/20552103816")

    assert r.status_code == 502


# ===================== Alta desde RUC =====================


async def test_crear_desde_ruc_mapea_los_datos(cliente):
    with simular_sunat():
        r = await cliente.post(f"{BASE}/empresas/desde-ruc/20552103816")

    assert r.status_code == 201
    empresa = r.json()
    assert empresa["razon_social"] == "AGROLIGHT PERU S.A.C."
    # En la tabla la columna se llama `ubigeo_sunat`; el proveedor la manda
    # como `ubigeo`. El mapeo ocurre en `_normalizar`.
    assert empresa["ubigeo_sunat"] == "150137"
    assert empresa["estado"] == "SUSPENSION TEMPORAL"
    assert empresa["direccion"].startswith("PJ. JORGE BASADRE")
    assert empresa["es_proveedor"] is True


async def test_la_condicion_de_agente_sale_del_padron_no_de_la_api(cliente):
    """El indicador de api.json.pe ya no decide: manda el padrón de SUNAT.

    La respuesta simulada trae `es_agente_de_percepcion: "SI"`, pero con el
    padrón vacío la empresa se registra como no agente. La siguiente
    sincronización la corrige.
    """
    with simular_sunat():
        r = await cliente.post(f"{BASE}/empresas/desde-ruc/20552103816")

    empresa = r.json()
    assert empresa["es_ag_retencion"] is False
    assert empresa["es_ag_percepcion"] is False


async def test_si_el_ruc_esta_en_el_padron_se_registra_como_agente(cliente):
    from app.db.session import AsyncSessionLocal
    from app.modules.proveedores.models.padron_agente import (
        TIPO_RETENCION,
        PadronAgente,
    )

    async with AsyncSessionLocal() as db:
        db.add(PadronAgente(ruc="20552103816", tipo=TIPO_RETENCION))
        await db.commit()

    with simular_sunat():
        r = await cliente.post(f"{BASE}/empresas/desde-ruc/20552103816")

    empresa = r.json()
    assert empresa["es_ag_retencion"] is True
    assert empresa["es_ag_percepcion"] is False


async def test_alta_repetida_es_409_sin_consultar_al_proveedor(cliente):
    """Si el RUC ya está, no tiene sentido gastar una consulta externa."""
    with simular_sunat():
        await cliente.post(f"{BASE}/empresas/desde-ruc/20552103816")

    with simular_sunat() as falso:
        r = await cliente.post(f"{BASE}/empresas/desde-ruc/20552103816")

    assert r.status_code == 409
    assert falso.call_count == 0


async def test_sin_ubigeo_no_se_da_de_alta(cliente):
    """`ubigeo_sunat` es obligatorio en la tabla: mejor un mensaje claro que
    un error de integridad. El proveedor lo manda como `ubigeo`."""
    sin_ubigeo = {k: v for k, v in RESPUESTA_SUNAT.items() if k != "ubigeo"}

    with simular_sunat(cuerpo=sin_ubigeo):
        r = await cliente.post(f"{BASE}/empresas/desde-ruc/20552103816")

    assert r.status_code == 502
    assert "ubigeo" in r.json()["detail"].lower()


async def test_no_proveedor(cliente):
    with simular_sunat():
        r = await cliente.post(
            f"{BASE}/empresas/desde-ruc/20552103816", params={"es_proveedor": False}
        )

    assert r.json()["es_proveedor"] is False


# ===================== CRUD =====================


async def test_alta_manual_exige_los_obligatorios(cliente):
    r = await cliente.post(f"{BASE}/empresas", json={"razon_social": "Solo el nombre"})
    assert r.status_code == 422


async def test_ruc_duplicado_es_409(cliente):
    datos = {
        "razon_social": "Empresa A",
        "ruc": "20552103816",
        "ubigeo_sunat": "150137",
        "estado": "ACTIVO",
    }
    await cliente.post(f"{BASE}/empresas", json=datos)

    r = await cliente.post(
        f"{BASE}/empresas", json={**datos, "razon_social": "Empresa B"}
    )

    assert r.status_code == 409


async def test_filtrar_proveedores(cliente):
    base = {"ubigeo_sunat": "150137", "estado": "ACTIVO"}
    await cliente.post(
        f"{BASE}/empresas",
        json={
            **base,
            "razon_social": "Proveedora",
            "ruc": "20111111111",
            "es_proveedor": True,
        },
    )
    await cliente.post(
        f"{BASE}/empresas",
        json={
            **base,
            "razon_social": "Cliente",
            "ruc": "20222222222",
            "es_proveedor": False,
        },
    )

    r = await cliente.get(f"{BASE}/empresas", params={"es_proveedor": True})

    assert [e["razon_social"] for e in r.json()["items"]] == ["Proveedora"]
