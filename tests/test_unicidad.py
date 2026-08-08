"""Tests de la regla de no duplicados.

Cubren las dos capas: la comprobación del servicio (que da un 409 explicando
qué campo se repite) y los índices únicos de la base, que son la garantía real.
"""

from __future__ import annotations

BASE = "/api/v1"


# ===================== Nombre =====================


async def test_nombre_repetido_es_409(cliente):
    await cliente.post(f"{BASE}/familias", json={"nombre": "Bebidas"})

    r = await cliente.post(f"{BASE}/familias", json={"nombre": "Bebidas"})

    assert r.status_code == 409
    assert "nombre" in r.json()["detail"]


async def test_el_duplicado_ignora_mayusculas_y_espacios(cliente):
    """Para quien carga el catálogo, "Bebidas" y " bebidas " son lo mismo."""
    await cliente.post(f"{BASE}/familias", json={"nombre": "Bebidas"})

    for variante in ("bebidas", "BEBIDAS", "  Bebidas  "):
        r = await cliente.post(f"{BASE}/familias", json={"nombre": variante})
        assert r.status_code == 409, f"debería rechazar {variante!r}"


# ===================== Código =====================


async def test_codigo_repetido_es_409(cliente):
    await cliente.post(f"{BASE}/familias", json={"nombre": "Bebidas", "codigo": "BEB"})

    r = await cliente.post(f"{BASE}/familias", json={"nombre": "Otra", "codigo": "BEB"})

    assert r.status_code == 409
    assert "codigo" in r.json()["detail"]


async def test_varios_sin_codigo_conviven(cliente):
    """El código es opcional: los vacíos no compiten entre sí."""
    primera = await cliente.post(f"{BASE}/familias", json={"nombre": "Una"})
    segunda = await cliente.post(f"{BASE}/familias", json={"nombre": "Otra"})

    assert primera.status_code == 201
    assert segunda.status_code == 201


# ===================== Ámbito =====================


async def test_el_nombre_se_repite_bajo_otro_padre(cliente):
    """Dos familias distintas pueden tener una sub familia "Granos"."""
    a = (await cliente.post(f"{BASE}/familias", json={"nombre": "Familia A"})).json()
    b = (await cliente.post(f"{BASE}/familias", json={"nombre": "Familia B"})).json()

    en_a = await cliente.post(
        f"{BASE}/sub-familias", json={"nombre": "Granos", "familia_id": a["id"]}
    )
    en_b = await cliente.post(
        f"{BASE}/sub-familias", json={"nombre": "Granos", "familia_id": b["id"]}
    )

    assert en_a.status_code == 201
    assert en_b.status_code == 201


async def test_el_nombre_no_se_repite_bajo_el_mismo_padre(cliente):
    familia = (await cliente.post(f"{BASE}/familias", json={"nombre": "Familia"})).json()
    await cliente.post(
        f"{BASE}/sub-familias", json={"nombre": "Granos", "familia_id": familia["id"]}
    )

    r = await cliente.post(
        f"{BASE}/sub-familias", json={"nombre": "Granos", "familia_id": familia["id"]}
    )

    assert r.status_code == 409


# ===================== Edición =====================


async def test_editar_hacia_un_duplicado_es_409(cliente):
    await cliente.post(f"{BASE}/familias", json={"nombre": "Bebidas"})
    otra = (await cliente.post(f"{BASE}/familias", json={"nombre": "Limpieza"})).json()

    r = await cliente.patch(f"{BASE}/familias/{otra['id']}", json={"nombre": "Bebidas"})

    assert r.status_code == 409


async def test_editar_sin_cambiar_el_nombre_no_choca_consigo_mismo(cliente):
    familia = (await cliente.post(f"{BASE}/familias", json={"nombre": "Bebidas"})).json()

    r = await cliente.patch(f"{BASE}/familias/{familia['id']}", json={"nombre": "Bebidas"})

    assert r.status_code == 200


async def test_mover_de_padre_puede_volverlo_duplicado(cliente):
    """Al editar hay que mirar el registro completo, no solo lo que llega:
    cambiar el padre puede volver duplicado un nombre que no lo era."""
    a = (await cliente.post(f"{BASE}/familias", json={"nombre": "Familia A"})).json()
    b = (await cliente.post(f"{BASE}/familias", json={"nombre": "Familia B"})).json()
    await cliente.post(
        f"{BASE}/sub-familias", json={"nombre": "Granos", "familia_id": a["id"]}
    )
    en_b = (
        await cliente.post(
            f"{BASE}/sub-familias", json={"nombre": "Granos", "familia_id": b["id"]}
        )
    ).json()

    # Mover la de B a A la deja conviviendo con otra "Granos" en la misma familia.
    r = await cliente.patch(
        f"{BASE}/sub-familias/{en_b['id']}", json={"familia_id": a["id"]}
    )

    assert r.status_code == 409


# ===================== La base como garantía =====================


async def test_el_indice_unico_existe_en_la_base(cliente):
    """La comprobación del servicio no basta: dos peticiones simultáneas
    pasarían las dos. El índice de la base es lo que realmente lo impide."""
    from sqlalchemy import text

    from app.db.session import engine

    async with engine.connect() as conexion:
        indices = {
            fila[0]
            for fila in await conexion.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE schemaname='public' AND indexname LIKE 'uq_%'"
                )
            )
        }

    esperados = {
        "uq_familias_nombre",
        "uq_familias_codigo",
        "uq_sub_familias_familia_nombre",
        "uq_categorias_sub_familia_nombre",
        "uq_sub_categorias_categoria_nombre",
        "uq_presentaciones_descripcion",
        "uq_productos_sku",
        "uq_productos_codigo_barras",
    }
    assert esperados <= indices


async def test_la_base_rechaza_el_duplicado_saltandose_el_servicio(cliente):
    """Inserta por SQL directo, sin pasar por la validación del servicio: debe
    fallar igual. Es lo que protege ante dos altas concurrentes."""
    import pytest
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from app.db.session import engine

    await cliente.post(f"{BASE}/familias", json={"nombre": "Bebidas"})

    with pytest.raises(IntegrityError):
        async with engine.begin() as conexion:
            await conexion.execute(
                text("INSERT INTO familias (nombre) VALUES (:n)"),
                {"n": "  BEBIDAS  "},
            )
