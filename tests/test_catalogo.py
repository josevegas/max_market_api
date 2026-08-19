"""Tests del maestro de productos: CRUD, jerarquía, filtros y baja lógica."""

from __future__ import annotations

from uuid import uuid4

from tests.conftest import producto_valido

BASE = "/api/v1"


# ===================== Alta y lectura =====================


async def test_crear_familia_devuelve_auditoria_del_servidor(cliente):
    """El cliente no manda `is_active` ni fechas: las pone el servidor."""
    r = await cliente.post(
        f"{BASE}/familias", json={"nombre": "Bebidas", "codigo": "BEB"}
    )

    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["is_active"] is True
    assert cuerpo["created_at"] and cuerpo["updated_at"]
    assert cuerpo["id"]


async def test_crear_familia_ignora_auditoria_enviada_por_el_cliente(cliente):
    """Aunque manden `is_active: false`, no debe colarse: es campo del servidor."""
    r = await cliente.post(
        f"{BASE}/familias", json={"nombre": "Bebidas", "is_active": False}
    )

    assert r.status_code == 201
    assert r.json()["is_active"] is True


async def test_listar_vacio_devuelve_lista(cliente):
    r = await cliente.get(f"{BASE}/familias")
    assert r.status_code == 200
    assert r.json()["items"] == []


async def test_obtener_por_id(cliente):
    creada = (await cliente.post(f"{BASE}/familias", json={"nombre": "Lácteos"})).json()

    r = await cliente.get(f"{BASE}/familias/{creada['id']}")

    assert r.status_code == 200
    assert r.json()["nombre"] == "Lácteos"


async def test_obtener_inexistente_es_404(cliente):
    r = await cliente.get(f"{BASE}/familias/{uuid4()}")
    assert r.status_code == 404


async def test_id_mal_formado_es_422(cliente):
    r = await cliente.get(f"{BASE}/familias/no-es-un-uuid")
    assert r.status_code == 422


# ===================== Jerarquía =====================


async def test_jerarquia_completa(cliente, catalogo):
    """familia → sub familia → categoría → sub categoría, cada una apuntando
    a su padre."""
    sub_familia = (
        await cliente.get(f"{BASE}/sub-familias/{catalogo['sub_familia_id']}")
    ).json()
    categoria = (
        await cliente.get(f"{BASE}/categorias/{catalogo['categoria_id']}")
    ).json()
    sub_categoria = (
        await cliente.get(f"{BASE}/sub-categorias/{catalogo['sub_categoria_id']}")
    ).json()

    assert sub_familia["familia_id"] == catalogo["familia_id"]
    assert categoria["sub_familia_id"] == catalogo["sub_familia_id"]
    assert sub_categoria["categoria_id"] == catalogo["categoria_id"]


async def test_referencia_a_padre_inexistente_es_400(cliente):
    """Una FK que no existe se traduce a 400, no a un 500 de integridad."""
    r = await cliente.post(
        f"{BASE}/sub-familias", json={"nombre": "Huérfana", "familia_id": str(uuid4())}
    )
    assert r.status_code == 400


async def test_filtrar_por_padre(cliente, catalogo):
    otra = (await cliente.post(f"{BASE}/familias", json={"nombre": "Otra"})).json()
    await cliente.post(
        f"{BASE}/sub-familias", json={"nombre": "Suelta", "familia_id": otra["id"]}
    )

    r = await cliente.get(
        f"{BASE}/sub-familias", params={"familia_id": catalogo["familia_id"]}
    )

    assert r.status_code == 200
    assert [s["nombre"] for s in r.json()["items"]] == ["Granos"]


# ===================== Edición =====================


async def test_patch_solo_toca_lo_enviado(cliente, catalogo):
    """Es el fallo clásico de un PATCH mal hecho: pisar con null lo omitido."""
    producto = (
        await cliente.post(f"{BASE}/productos", json=producto_valido(catalogo))
    ).json()

    r = await cliente.patch(
        f"{BASE}/productos/{producto['id']}", json={"descripcion_web": "Arroz Premium"}
    )

    assert r.status_code == 200
    assert r.json()["descripcion_web"] == "Arroz Premium"
    assert r.json()["sku"] == producto["sku"]
    assert r.json()["descripcion_legal"] == producto["descripcion_legal"]


async def test_actualizar_inexistente_es_404(cliente):
    r = await cliente.patch(f"{BASE}/familias/{uuid4()}", json={"nombre": "X"})
    assert r.status_code == 404


# ===================== Baja lógica =====================


async def test_baja_logica_conserva_la_fila(cliente):
    familia = (
        await cliente.post(f"{BASE}/familias", json={"nombre": "Temporal"})
    ).json()

    r = await cliente.delete(f"{BASE}/familias/{familia['id']}")

    assert r.status_code == 200
    assert r.json()["is_active"] is False
    # La fila sigue existiendo: los catálogos están referenciados por productos
    # y borrarlos de verdad rompería el histórico.
    assert (await cliente.get(f"{BASE}/familias/{familia['id']}")).status_code == 200


async def test_los_inactivos_no_se_listan_por_defecto(cliente):
    familia = (
        await cliente.post(f"{BASE}/familias", json={"nombre": "Temporal"})
    ).json()
    await cliente.delete(f"{BASE}/familias/{familia['id']}")

    activas = (await cliente.get(f"{BASE}/familias")).json()
    todas = (
        await cliente.get(f"{BASE}/familias", params={"solo_activos": False})
    ).json()

    assert activas["items"] == []
    assert todas["total"] == 1


# ===================== Productos =====================


async def test_crear_producto_completo(cliente, catalogo):
    r = await cliente.post(f"{BASE}/productos", json=producto_valido(catalogo))

    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["sku"] == "ARR-EXT-5K"
    assert cuerpo["presentacion_id"] == catalogo["presentacion_id"]


async def test_producto_sin_sub_categoria(cliente, catalogo):
    """La sub categoría es opcional en el modelo; el schema debe respetarlo."""
    datos = producto_valido(catalogo, sku="MIN-001")
    datos["sub_categoria_id"] = None

    r = await cliente.post(f"{BASE}/productos", json=datos)

    assert r.status_code == 201
    assert r.json()["sub_categoria_id"] is None


async def test_producto_sin_presentacion_es_422(cliente, catalogo):
    """La presentación sí es obligatoria: debe rechazarse en la validación,
    no llegar a la base y volver como error de integridad."""
    datos = producto_valido(catalogo, sku="MIN-002")
    datos["presentacion_id"] = None

    r = await cliente.post(f"{BASE}/productos", json=datos)

    assert r.status_code == 422


async def test_producto_sin_campos_obligatorios_es_422(cliente, catalogo):
    r = await cliente.post(f"{BASE}/productos", json={"sku": "SOLO-SKU"})
    assert r.status_code == 422


async def test_buscar_producto_por_sku(cliente, catalogo):
    await cliente.post(f"{BASE}/productos", json=producto_valido(catalogo))

    r = await cliente.get(f"{BASE}/productos/sku/ARR-EXT-5K")

    assert r.status_code == 200
    assert r.json()["descripcion_corta"] == "Arroz extra 5kg"


async def test_buscar_sku_inexistente_es_404(cliente):
    assert (await cliente.get(f"{BASE}/productos/sku/NO-EXISTE")).status_code == 404


async def test_filtrar_productos_por_categoria(cliente, catalogo):
    await cliente.post(f"{BASE}/productos", json=producto_valido(catalogo))

    # Se lee `total` y no `len(items)`: el total refleja todo lo que cumple el
    # filtro, aunque la página devuelta sea más corta.
    conteo = (
        await cliente.get(
            f"{BASE}/productos", params={"categoria_id": catalogo["categoria_id"]}
        )
    ).json()["total"]
    sin_coincidencias = (
        await cliente.get(f"{BASE}/productos", params={"categoria_id": str(uuid4())})
    ).json()["total"]

    assert conteo == 1
    assert sin_coincidencias == 0


# ===================== Precios =====================


async def test_precio_vigente(cliente, catalogo):
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

    r = await cliente.get(f"{BASE}/productos/{producto['id']}/precio-vigente")

    assert r.status_code == 200
    # Decimal, no float: los importes no pueden arrastrar error de redondeo.
    # El de venta lo calcula el servidor (ver `test_precio_venta`).
    assert r.json()["precio_venta"] == "14.58"


async def test_producto_sin_precio_vigente_es_404(cliente, catalogo):
    producto = (
        await cliente.post(f"{BASE}/productos", json=producto_valido(catalogo))
    ).json()

    r = await cliente.get(f"{BASE}/productos/{producto['id']}/precio-vigente")

    assert r.status_code == 404


async def test_precio_con_vigencia_invertida_es_422(cliente, catalogo):
    producto = (
        await cliente.post(f"{BASE}/productos", json=producto_valido(catalogo))
    ).json()

    r = await cliente.post(
        f"{BASE}/precios",
        json={
            "producto_id": producto["id"],
            "precio_compra": "1.00",
            "precio_venta": "2.00",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-01-01",
        },
    )

    assert r.status_code == 422


async def test_precio_negativo_es_422(cliente, catalogo):
    producto = (
        await cliente.post(f"{BASE}/productos", json=producto_valido(catalogo))
    ).json()

    r = await cliente.post(
        f"{BASE}/precios",
        json={
            "producto_id": producto["id"],
            "precio_compra": "-1.00",
            "precio_venta": "2.00",
            "fecha_inicio": "2026-01-01",
        },
    )

    assert r.status_code == 422


async def test_historial_de_precios(cliente, catalogo):
    producto = (
        await cliente.post(f"{BASE}/productos", json=producto_valido(catalogo))
    ).json()
    for inicio, venta in (("2024-01-01", "10.00"), ("2025-01-01", "12.00")):
        await cliente.post(
            f"{BASE}/precios",
            json={
                "producto_id": producto["id"],
                "precio_compra": "8.00",
                "precio_venta": venta,
                "fecha_inicio": inicio,
            },
        )

    r = await cliente.get(f"{BASE}/productos/{producto['id']}/precios")

    assert r.status_code == 200
    assert len(r.json()["items"]) == 2
