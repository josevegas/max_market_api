"""Comprobaciones de que la API levanta y la infraestructura responde."""

from __future__ import annotations


async def test_salud_responde(cliente):
    r = await cliente.get("/salud")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok"


async def test_raiz_orienta_en_vez_de_404(cliente):
    """La raíz devolvía un 404 seco que parecía que la API no había levantado."""
    r = await cliente.get("/")
    assert r.status_code == 200
    assert r.json()["documentacion"] == "/docs"


async def test_openapi_se_genera(cliente):
    """Si un handler tiene un tipo irresoluble, el OpenAPI revienta: esto lo
    detecta sin tener que recorrer endpoint por endpoint."""
    r = await cliente.get("/openapi.json")
    assert r.status_code == 200
    assert "/api/v1/productos" in r.json()["paths"]
