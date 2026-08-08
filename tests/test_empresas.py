"""Tests de empresas y de la consulta de RUC.

La API externa (api.json.pe) se simula: un test no debe depender de que un
tercero esté arriba, ni gastar cuota de la cuenta, ni cambiar de resultado
porque SUNAT actualizó un dato.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

BASE = "/api/v1"

#: Respuesta real de api.json.pe para el RUC 20552103816, recortada a lo que
#: se usa. Sirve de contrato: si el proveedor cambia estos nombres, los tests
#: lo notan antes que producción.
RESPUESTA_SUNAT = {
    "ruc": "20552103816",
    "nombre_o_razon_social": "AGROLIGHT PERU S.A.C.",
    "direccion": "PJ. JORGE BASADRE NRO. 158",
    "direccion_completa": "PJ. JORGE BASADRE NRO. 158 URB. POP LA UNIVERSAL",
    "ubigeo_sunat": "150137",
    "estado": "ACTIVO",
    "condicion": "HABIDO",
    "es_agente_de_retencion": "NO",
    "es_agente_de_percepcion": "SI",
    "departamento": "LIMA",
}


class RespuestaFalsa:
    """Imita lo que `requests.post` devuelve, con lo que usa el servicio."""

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
        "app.modules.proveedores.services.empresa_service.requests.post",
        return_value=RespuestaFalsa(cuerpo, status_code),
    )


# ===================== Consulta de RUC =====================


async def test_consultar_ruc_normaliza_la_respuesta(cliente):
    with simular_sunat():
        r = await cliente.get(f"{BASE}/empresas/ruc/20552103816")

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["razon_social"] == "AGROLIGHT PERU S.A.C."
    assert cuerpo["ubigeo_sunat"] == "150137"
    assert cuerpo["direccion_completa"].startswith("PJ. JORGE BASADRE")
    # Se conserva la respuesta completa: el proveedor no garantiza una forma
    # fija y ahí queda lo que no se mapeó.
    assert cuerpo["crudo"]["departamento"] == "LIMA"


async def test_consultar_ruc_envia_el_token_y_el_cuerpo_esperados(cliente):
    """El contrato con el proveedor: POST con `{"ruc": ...}` y Bearer."""
    with simular_sunat() as falso:
        await cliente.get(f"{BASE}/empresas/ruc/20552103816")

    _, kwargs = falso.call_args
    assert kwargs["json"] == {"ruc": "20552103816"}
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
        "app.modules.proveedores.services.empresa_service.requests.post",
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
    assert empresa["ubigeo_sunat"] == "150137"
    assert empresa["estado"] == "ACTIVO"
    assert empresa["es_proveedor"] is True


async def test_los_indicadores_si_no_se_vuelven_booleanos(cliente):
    """SUNAT responde "SI"/"NO", no booleanos."""
    with simular_sunat():
        r = await cliente.post(f"{BASE}/empresas/desde-ruc/20552103816")

    empresa = r.json()
    assert empresa["es_ag_retencion"] is False  # venía "NO"
    assert empresa["es_ag_percepcion"] is True  # venía "SI"


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
    un error de integridad."""
    sin_ubigeo = {k: v for k, v in RESPUESTA_SUNAT.items() if k != "ubigeo_sunat"}

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

    r = await cliente.post(f"{BASE}/empresas", json={**datos, "razon_social": "Empresa B"})

    assert r.status_code == 409


async def test_filtrar_proveedores(cliente):
    base = {"ubigeo_sunat": "150137", "estado": "ACTIVO"}
    await cliente.post(
        f"{BASE}/empresas",
        json={**base, "razon_social": "Proveedora", "ruc": "20111111111", "es_proveedor": True},
    )
    await cliente.post(
        f"{BASE}/empresas",
        json={**base, "razon_social": "Cliente", "ruc": "20222222222", "es_proveedor": False},
    )

    r = await cliente.get(f"{BASE}/empresas", params={"es_proveedor": True})

    assert [e["razon_social"] for e in r.json()] == ["Proveedora"]
