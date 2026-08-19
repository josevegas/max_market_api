"""Contrato con el frontend Angular.

Estos tests no prueban lógica de negocio: vigilan que la API siga hablando el
idioma que el frontend espera. Un cambio de nombre de campo o un error con otra
forma no rompe ningún test de negocio, pero deja la pantalla en blanco.

Cada lista de campos refleja lo que consume `max_market_frontend`
(`features/productos/models/catalogo.model.ts` y los servicios). Si acá se
cambia algo, hay que cambiarlo también allá — y al revés.
"""

from __future__ import annotations

from tests.conftest import producto_valido

BASE = "/api/v1"
ORIGEN_FRONTEND = "http://localhost:4300"

#: Campos de auditoría que el frontend declara en `Auditoria`.
AUDITORIA = {"id", "is_active", "created_at", "updated_at", "created_by", "updated_by"}


# ===================== CORS =====================


async def test_preflight_desde_el_frontend(cliente):
    """Antes de un POST con JSON el navegador manda un OPTIONS. Si falla, la
    petición real ni se intenta y en consola solo se ve un error de CORS."""
    r = await cliente.options(
        f"{BASE}/familias",
        headers={
            "Origin": ORIGEN_FRONTEND,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == ORIGEN_FRONTEND
    for metodo in ("GET", "POST", "PATCH", "DELETE"):
        assert metodo in r.headers["access-control-allow-methods"]


async def test_las_respuestas_llevan_la_cabecera_de_origen(cliente):
    r = await cliente.get(f"{BASE}/familias", headers={"Origin": ORIGEN_FRONTEND})

    assert r.headers.get("access-control-allow-origin") == ORIGEN_FRONTEND


async def test_un_origen_ajeno_no_recibe_permiso(cliente):
    r = await cliente.get(
        f"{BASE}/familias", headers={"Origin": "http://ajeno.example"}
    )

    # Sin la cabecera, el navegador descarta la respuesta.
    assert "access-control-allow-origin" not in r.headers


# ===================== Forma de las respuestas =====================


async def test_campos_de_familia(cliente):
    creada = (
        await cliente.post(f"{BASE}/familias", json={"nombre": "Abarrotes"})
    ).json()

    assert set(creada) == AUDITORIA | {"nombre", "codigo"}


async def test_campos_de_sub_familia(cliente, catalogo):
    r = await cliente.get(f"{BASE}/sub-familias/{catalogo['sub_familia_id']}")

    assert set(r.json()) == AUDITORIA | {"nombre", "codigo", "familia_id"}


async def test_campos_de_categoria(cliente, catalogo):
    r = await cliente.get(f"{BASE}/categorias/{catalogo['categoria_id']}")

    assert set(r.json()) == AUDITORIA | {
        "nombre",
        "codigo",
        "sub_familia_id",
        "margen_ganancia",
    }


async def test_campos_de_sub_categoria(cliente, catalogo):
    r = await cliente.get(f"{BASE}/sub-categorias/{catalogo['sub_categoria_id']}")

    assert set(r.json()) == AUDITORIA | {"nombre", "codigo", "categoria_id"}


async def test_campos_de_presentacion(cliente, catalogo):
    r = await cliente.get(f"{BASE}/presentaciones/{catalogo['presentacion_id']}")

    assert set(r.json()) == AUDITORIA | {"descripcion", "codigo"}


async def test_campos_de_producto(cliente, catalogo):
    r = await cliente.post(f"{BASE}/productos", json=producto_valido(catalogo))

    assert set(r.json()) == AUDITORIA | {
        "tipo_producto",
        "sku",
        "codigo_barras",
        "codigo_sunat",
        "descripcion_corta",
        "descripcion_legal",
        "descripcion_compra",
        "descripcion_web",
        "familia_id",
        "sub_familia_id",
        "categoria_id",
        "sub_categoria_id",
        "presentacion_id",
        "marca_fabricante",
        "unidad_compra",
        "unidad_venta",
    }


async def test_los_importes_viajan_como_texto(cliente, catalogo):
    """El frontend los tipa `string | number` porque el backend serializa
    Decimal como texto: en float se perdería precisión en los centavos."""
    producto = (
        await cliente.post(f"{BASE}/productos", json=producto_valido(catalogo))
    ).json()
    await cliente.post(
        f"{BASE}/precios",
        json={
            "producto_id": producto["id"],
            "precio_compra": "12.30",
            "fecha_inicio": "2020-01-01",
        },
    )

    precio = (
        await cliente.get(f"{BASE}/productos/{producto['id']}/precio-vigente")
    ).json()

    # 12.30 con el 18.5% de la categoría de la fixture. El número lo fija
    # `test_precio_venta`; acá lo que importa es que viaje como texto.
    assert precio["precio_venta"] == "14.58"
    assert isinstance(precio["precio_venta"], str)


# ===================== Listados =====================


async def test_los_listados_vienen_paginados(cliente):
    """El frontend lee `items` y usa `total` para el paginador.

    Este test decía lo contrario —que la respuesta era un array plano— porque
    ese era el contrato anterior. Se cambió a propósito: sin `total`, quien
    recibía 50 filas no podía distinguir «esto es todo» de «hay más», y las
    tablas pedían `limite=500` por si acaso.
    """
    await cliente.post(f"{BASE}/familias", json={"nombre": "Abarrotes"})

    cuerpo = (await cliente.get(f"{BASE}/familias")).json()

    assert set(cuerpo) == {"items", "total", "limite", "desplazamiento"}
    assert isinstance(cuerpo["items"], list)
    assert isinstance(cuerpo["items"][0], dict)
    assert cuerpo["total"] == 1


async def test_el_total_cuenta_mas_alla_de_la_pagina(cliente):
    """Es lo que permite pintar el paginador sin adivinar cuántas páginas hay."""
    for i in range(5):
        await cliente.post(f"{BASE}/familias", json={"nombre": f"Familia {i}"})

    cuerpo = (await cliente.get(f"{BASE}/familias", params={"limite": 2})).json()

    assert len(cuerpo["items"]) == 2
    assert cuerpo["total"] == 5
    assert cuerpo["limite"] == 2
    assert cuerpo["desplazamiento"] == 0


async def test_el_desplazamiento_avanza_de_pagina(cliente):
    for i in range(5):
        await cliente.post(f"{BASE}/familias", json={"nombre": f"Familia {i}"})

    primera = (await cliente.get(f"{BASE}/familias", params={"limite": 2})).json()
    tercera = (
        await cliente.get(f"{BASE}/familias", params={"limite": 2, "desplazamiento": 4})
    ).json()

    assert len(tercera["items"]) == 1, "la última página va incompleta"
    assert tercera["total"] == 5
    ids_primera = {f["id"] for f in primera["items"]}
    assert not ids_primera & {f["id"] for f in tercera["items"]}


async def test_los_parametros_de_listado_que_usa_el_frontend(cliente, catalogo):
    """`solo_activos`, `limite` y los filtros por padre: son los que manda."""
    r = await cliente.get(
        f"{BASE}/sub-familias",
        params={
            "solo_activos": True,
            "limite": 500,
            "desplazamiento": 0,
            "familia_id": catalogo["familia_id"],
        },
    )

    assert r.status_code == 200


# ===================== Forma de los errores =====================


async def test_el_error_de_negocio_trae_detail_de_texto(cliente):
    """El `ApiClient` del frontend saca el mensaje de `detail` y lo muestra en
    el toast; si dejara de ser texto, el usuario vería "[object Object]"."""
    await cliente.post(f"{BASE}/familias", json={"nombre": "Abarrotes"})

    r = await cliente.post(f"{BASE}/familias", json={"nombre": "Abarrotes"})

    assert r.status_code == 409
    assert isinstance(r.json()["detail"], str)


async def test_el_error_de_validacion_trae_loc_y_msg(cliente):
    """En un 422 el `detail` es una lista; el frontend arma el mensaje con
    `loc` y `msg` de cada entrada."""
    r = await cliente.post(f"{BASE}/familias", json={})

    assert r.status_code == 422
    detalle = r.json()["detail"]
    assert isinstance(detalle, list)
    assert {"loc", "msg"} <= set(detalle[0])


async def test_el_404_trae_detail_de_texto(cliente):
    from uuid import uuid4

    r = await cliente.get(f"{BASE}/familias/{uuid4()}")

    assert r.status_code == 404
    assert isinstance(r.json()["detail"], str)


# ===================== Rutas que el frontend invoca =====================


async def test_todas_las_rutas_que_usa_el_frontend_existen(cliente):
    """Recorre el OpenAPI en vez de llamarlas una a una: detecta un cambio de
    prefijo (por ejemplo `sub-familias` → `subfamilias`) al instante."""
    rutas = set((await cliente.get("/openapi.json")).json()["paths"])

    esperadas = {
        f"{BASE}/familias",
        f"{BASE}/familias/{{registro_id}}",
        f"{BASE}/sub-familias",
        f"{BASE}/sub-familias/{{registro_id}}",
        f"{BASE}/categorias",
        f"{BASE}/categorias/{{registro_id}}",
        f"{BASE}/sub-categorias",
        f"{BASE}/sub-categorias/{{registro_id}}",
        f"{BASE}/presentaciones",
        f"{BASE}/presentaciones/{{registro_id}}",
        f"{BASE}/productos",
        f"{BASE}/productos/{{registro_id}}",
        f"{BASE}/productos/sku/{{sku}}",
        f"{BASE}/productos/{{producto_id}}/precios",
        f"{BASE}/productos/{{producto_id}}/precio-vigente",
        f"{BASE}/precios",
    }

    assert esperadas <= rutas, f"faltan: {sorted(esperadas - rutas)}"
