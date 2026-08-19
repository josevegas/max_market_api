"""El comparativo que decide qué cotización conviene aprobar.

Cuatro criterios pesados: precio 35%, entrega 25%, stock atendido 20%, condición
de pago 20%. Lo que se prueba acá es que el puntaje diga lo que dice que dice —y
sobre todo que **no** premie al proveedor que cotiza menos, que es el error que
tendría un comparativo por monto total—.

La mitad de arriba son pruebas de `_puntuar`, que es una función pura: la
aritmética del puntaje se puede acorralar sin montar la cadena entera, y los
casos borde (todos iguales, valores en cero, valores sin medir) son justo donde
una fórmula de normalización se rompe.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.movimientos.constantes import (
    CODIGO_APROBADO,
    CODIGO_OBSERVADO,
    CODIGO_PENDIENTE,
    CODIGO_RECHAZADO,
)
from app.modules.movimientos.services.comparativo_service import PESOS, _puntuar
from tests.conftest import producto_valido

BASE = "/api/v1"


# ===================== La aritmética del puntaje =====================


def test_los_pesos_suman_cien():
    """Si no suman 100, el puntaje total deja de ser sobre 100 y el "óptimo"
    seguiría saliendo pero ya no querría decir lo mismo."""
    assert sum(PESOS.values()) == 100


def test_los_cuatro_criterios_estan():
    assert set(PESOS) == {"precio", "entrega", "stock", "pago"}


def test_el_peso_es_el_que_pidio_el_negocio():
    assert PESOS == {"precio": 35, "entrega": 25, "stock": 20, "pago": 20}


def test_menos_es_mejor_el_mas_barato_saca_cien():
    puntajes = _puntuar("precio", [Decimal("10"), Decimal("20")])
    assert puntajes == [Decimal("100"), Decimal("50")]


def test_mas_es_mejor_el_mayor_saca_cien():
    puntajes = _puntuar("pago", [Decimal("30"), Decimal("15")])
    assert puntajes == [Decimal("100"), Decimal("50")]


def test_una_diferencia_chica_da_un_puntaje_parecido():
    """La razón contra el mejor y no una posición en el ranking.

    Con una escala por posiciones estas dos quedarían en 100 y 0, y el
    comparativo afirmaría una diferencia enorme entre dos ofertas casi iguales.
    """
    puntajes = _puntuar("precio", [Decimal("100"), Decimal("110")])
    assert puntajes[0] == Decimal("100")
    assert Decimal("90") <= puntajes[1] <= Decimal("91")


def test_todos_iguales_empatan_en_cien():
    puntajes = _puntuar("entrega", [Decimal("7"), Decimal("7"), Decimal("7")])
    assert puntajes == [Decimal("100")] * 3


def test_nadie_da_credito_empatan_todos():
    """Todos al contado: el criterio no distingue, y repartir puntos ahí sería
    inventar una diferencia que no existe."""
    assert _puntuar("pago", [Decimal("0"), Decimal("0")]) == [
        Decimal("100"),
        Decimal("100"),
    ]


def test_entrega_inmediata_solo_la_iguala_otra_inmediata():
    """`mejor == 0` en "menos es mejor": la razón contra cero no existe, así que
    se resuelve como caso aparte y no dividiendo."""
    assert _puntuar("entrega", [Decimal("0"), Decimal("5")]) == [
        Decimal("100"),
        Decimal("0"),
    ]


def test_lo_que_no_se_puede_medir_saca_cero():
    """Una cotización sin líneas no tiene precio por unidad. Dejarla fuera del
    criterio la haría competir por 65 puntos mientras las demás compiten por
    100, y podría ganar sin haber cotizado nada."""
    assert _puntuar("precio", [Decimal("10"), None]) == [
        Decimal("100"),
        Decimal("0"),
    ]


def test_si_ninguna_se_puede_medir_todas_sacan_cero():
    assert _puntuar("precio", [None, None]) == [Decimal("0"), Decimal("0")]


# ===================== Utilidades de la cadena =====================


async def _estado(cliente, codigo: str) -> str:
    items = (await cliente.get(f"{BASE}/estados", params={"codigo": codigo})).json()[
        "items"
    ]
    assert items, f"falta el estado canónico '{codigo}'"
    return items[0]["id"]


async def _almacen(cliente) -> str:
    """El almacén del test, creándolo la primera vez.

    Se reutiliza a propósito, igual que en `test_cadena_compras`: un test que
    arma dos pedidos lo pide dos veces, y zona, sede y market tienen código
    único, así que el segundo intento chocaba con un 409 que no tenía nada que
    ver con lo que se estaba probando.
    """
    existentes = (await cliente.get(f"{BASE}/almacenes")).json()["items"]
    if existentes:
        return existentes[0]["id"]

    zona = (
        await cliente.post(f"{BASE}/zonas", json={"nombre": "Norte", "codigo": "NOR"})
    ).json()["id"]
    sede = (
        await cliente.post(
            f"{BASE}/sedes", json={"zona_id": zona, "nombre": "Lima", "codigo": "LIM"}
        )
    ).json()["id"]
    market = (
        await cliente.post(
            f"{BASE}/markets",
            json={"sede_id": sede, "nombre": "Market 1", "codigo": "MK1"},
        )
    ).json()["id"]
    r = await cliente.post(
        f"{BASE}/almacenes",
        json={"market_id": market, "nombre": "Central", "codigo": "ALM1"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _producto(cliente, catalogo: dict, sku: str) -> str:
    r = await cliente.post(f"{BASE}/productos", json=producto_valido(catalogo, sku))
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _proveedor(cliente, ruc: str, razon: str) -> str:
    r = await cliente.post(
        f"{BASE}/empresas",
        json={
            "razon_social": razon,
            "ruc": ruc,
            "ubigeo_sunat": "150101",
            "estado": "ACTIVO",
            "es_proveedor": True,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _pedido_con_lineas(cliente, catalogo, cantidades: dict[str, int]) -> str:
    """Un pedido pendiente que pide `cantidades[producto] `de cada producto.

    Se crea directo y no aprobando un requerimiento: acá no se prueba la
    generación de la cadena —eso está en `test_generacion_cadena`— sino cómo se
    puntúa lo que cuelga del pedido, y montar la cadena entera solo agregaría
    formas de fallar ajenas a lo que se mide.
    """
    almacen = await _almacen(cliente)
    req = (
        await cliente.post(
            f"{BASE}/requerimientos",
            json={
                "almacen_id": almacen,
                "estado_id": await _estado(cliente, CODIGO_APROBADO),
            },
        )
    ).json()["id"]
    # Nace aprobado y no se aprueba después: colgarle cotizaciones exige que lo
    # esté, y aprobarlo con un PATCH dispararía la generación automática de una
    # cotización por proveedor, que ensuciaría el cuadro que se quiere medir.
    r = await cliente.post(
        f"{BASE}/pedidos",
        json={
            "requerimiento_id": req,
            "estado_id": await _estado(cliente, CODIGO_APROBADO),
        },
    )
    assert r.status_code == 201, r.text
    pedido = r.json()["id"]

    for producto_id, cantidad in cantidades.items():
        r = await cliente.post(
            f"{BASE}/pedidos-detalle",
            json={
                "pedido_id": pedido,
                "producto_id": producto_id,
                "unidad_medida_id": catalogo["unidad_compra"],
                "cantidad": cantidad,
            },
        )
        assert r.status_code == 201, r.text
    return pedido


async def _cotizacion_con_lineas(
    cliente,
    catalogo,
    pedido: str,
    proveedor: str,
    lineas: dict[str, tuple[int, str]],
    tiempo_atencion: int = 0,
    condicion_pago_dias: int = 0,
) -> str:
    """Una cotización con `lineas[producto] = (cantidad, precio_unitario)`."""
    r = await cliente.post(
        f"{BASE}/cotizaciones",
        json={
            "pedido_id": pedido,
            "proveedor_id": proveedor,
            "tiempo_atencion": tiempo_atencion,
            "condicion_pago_dias": condicion_pago_dias,
        },
    )
    assert r.status_code == 201, r.text
    cot = r.json()["id"]

    for producto_id, (cantidad, precio) in lineas.items():
        r = await cliente.post(
            f"{BASE}/cotizaciones-detalle",
            json={
                "cotizacion_id": cot,
                "producto_id": producto_id,
                "unidad_medida_id": catalogo["unidad_compra"],
                "cantidad": cantidad,
                "precio_unitario": precio,
            },
        )
        assert r.status_code == 201, r.text
    return cot


async def _comparativo(cliente, pedido: str) -> dict:
    r = await cliente.get(f"{BASE}/pedidos/{pedido}/comparativo-cotizaciones")
    assert r.status_code == 200, r.text
    return r.json()


def _por_id(comparativo: dict, cotizacion_id: str) -> dict:
    fila = next(
        c for c in comparativo["cotizaciones"] if c["cotizacion_id"] == cotizacion_id
    )
    return fila


# ===================== El campo de condición de pago =====================


async def test_la_cotizacion_nace_al_contado(cliente, catalogo):
    """`condicion_pago_dias` es NOT NULL con default 0: la que nadie completó
    queda en el peor caso para el proveedor, no premiada por el dato faltante."""
    producto = await _producto(cliente, catalogo, "CMP-000")
    pedido = await _pedido_con_lineas(cliente, catalogo, {producto: 10})
    proveedor = await _proveedor(cliente, "20100000000", "UNO S.A.C.")

    r = await cliente.post(
        f"{BASE}/cotizaciones", json={"pedido_id": pedido, "proveedor_id": proveedor}
    )
    assert r.status_code == 201, r.text
    assert r.json()["condicion_pago_dias"] == 0


async def test_los_dias_de_credito_se_guardan_y_se_editan(cliente, catalogo):
    producto = await _producto(cliente, catalogo, "CMP-001")
    pedido = await _pedido_con_lineas(cliente, catalogo, {producto: 10})
    proveedor = await _proveedor(cliente, "20100000001", "DOS S.A.C.")

    cot = (
        await cliente.post(
            f"{BASE}/cotizaciones",
            json={
                "pedido_id": pedido,
                "proveedor_id": proveedor,
                "condicion_pago_dias": 30,
            },
        )
    ).json()
    assert cot["condicion_pago_dias"] == 30

    r = await cliente.patch(
        f"{BASE}/cotizaciones/{cot['id']}", json={"condicion_pago_dias": 60}
    )
    assert r.status_code == 200, r.text
    assert r.json()["condicion_pago_dias"] == 60


@pytest.mark.parametrize("dias", [-1, 366])
async def test_los_dias_de_credito_fuera_de_rango_se_rechazan(cliente, catalogo, dias):
    producto = await _producto(cliente, catalogo, f"CMP-R{abs(dias)}")
    pedido = await _pedido_con_lineas(cliente, catalogo, {producto: 10})
    proveedor = await _proveedor(cliente, f"2010000{abs(dias):04d}", "TRES S.A.C.")

    r = await cliente.post(
        f"{BASE}/cotizaciones",
        json={
            "pedido_id": pedido,
            "proveedor_id": proveedor,
            "condicion_pago_dias": dias,
        },
    )
    assert r.status_code == 422, r.text


# ===================== Cobertura (stock atendido) =====================


async def test_la_cobertura_es_lo_que_cubre_del_pedido(cliente, catalogo):
    """Dos productos de 100 y 50; cotizar solo el primero cubre 100 de 150."""
    uno = await _producto(cliente, catalogo, "CMP-010")
    dos = await _producto(cliente, catalogo, "CMP-011")
    pedido = await _pedido_con_lineas(cliente, catalogo, {uno: 100, dos: 50})
    proveedor = await _proveedor(cliente, "20100000010", "PARCIAL S.A.C.")

    cot = await _cotizacion_con_lineas(
        cliente, catalogo, pedido, proveedor, {uno: (100, "9.00")}
    )

    comparativo = await _comparativo(cliente, pedido)
    fila = _por_id(comparativo, cot)
    assert comparativo["unidades_pedidas"] == 150
    assert fila["unidades_atendidas"] == 100
    assert Decimal(fila["cobertura"]) == Decimal("66.67")
    assert fila["productos_sin_cotizar"] == [dos]


async def test_cotizar_de_mas_no_sube_la_cobertura(cliente, catalogo):
    """Se cuenta contra lo que el pedido pide, no contra lo que el proveedor
    ofrece: sin ese tope, mandar el doble daría 200% de cobertura."""
    producto = await _producto(cliente, catalogo, "CMP-012")
    pedido = await _pedido_con_lineas(cliente, catalogo, {producto: 10})
    proveedor = await _proveedor(cliente, "20100000011", "GENEROSA S.A.C.")

    cot = await _cotizacion_con_lineas(
        cliente, catalogo, pedido, proveedor, {producto: (999, "1.00")}
    )

    fila = _por_id(await _comparativo(cliente, pedido), cot)
    assert fila["unidades_atendidas"] == 10
    assert Decimal(fila["cobertura"]) == Decimal("100.00")


# ===================== Lo que no debe pasar: premiar al parcial =====================


async def test_el_precio_se_mide_por_unidad_y_no_por_monto_total(cliente, catalogo):
    """El caso que motiva todo el módulo.

    El parcial cotiza la mitad del pedido y su monto total es más bajo, pero su
    precio **por unidad** es más alto. Si el criterio de precio mirara el monto,
    el parcial ganaría los 35 puntos solo por cotizar menos.
    """
    uno = await _producto(cliente, catalogo, "CMP-020")
    dos = await _producto(cliente, catalogo, "CMP-021")
    pedido = await _pedido_con_lineas(cliente, catalogo, {uno: 100, dos: 50})

    completo = await _proveedor(cliente, "20100000020", "COMPLETA S.A.C.")
    parcial = await _proveedor(cliente, "20100000021", "PARCIAL S.A.C.")

    # 150 unidades por 1500 → 10.00 por unidad.
    cot_completo = await _cotizacion_con_lineas(
        cliente,
        catalogo,
        pedido,
        completo,
        {uno: (100, "10.00"), dos: (50, "10.00")},
    )
    # 100 unidades por 1100 → 11.00 por unidad: monto menor, precio peor.
    cot_parcial = await _cotizacion_con_lineas(
        cliente, catalogo, pedido, parcial, {uno: (100, "11.00")}
    )

    comparativo = await _comparativo(cliente, pedido)
    fila_completo = _por_id(comparativo, cot_completo)
    fila_parcial = _por_id(comparativo, cot_parcial)

    # El monto del parcial es menor...
    assert Decimal(fila_parcial["monto_total"]) < Decimal(fila_completo["monto_total"])
    # ...y aun así pierde el criterio de precio, porque cobra más por unidad.
    assert Decimal(fila_completo["precio_por_unidad"]) == Decimal("10.00")
    assert Decimal(fila_parcial["precio_por_unidad"]) == Decimal("11.00")
    assert Decimal(fila_completo["criterios"]["precio"]["puntaje"]) > Decimal(
        fila_parcial["criterios"]["precio"]["puntaje"]
    )
    assert fila_completo["optimo"] is True
    assert fila_parcial["optimo"] is False


# ===================== El óptimo =====================


async def test_el_optimo_es_el_de_mayor_puntaje_y_viene_primero(cliente, catalogo):
    producto = await _producto(cliente, catalogo, "CMP-030")
    pedido = await _pedido_con_lineas(cliente, catalogo, {producto: 100})

    bueno = await _proveedor(cliente, "20100000030", "BUENA S.A.C.")
    malo = await _proveedor(cliente, "20100000031", "MALA S.A.C.")

    # Gana los cuatro criterios: más barato, más rápido, cubre todo, más crédito.
    cot_bueno = await _cotizacion_con_lineas(
        cliente,
        catalogo,
        pedido,
        bueno,
        {producto: (100, "8.00")},
        tiempo_atencion=3,
        condicion_pago_dias=60,
    )
    await _cotizacion_con_lineas(
        cliente,
        catalogo,
        pedido,
        malo,
        {producto: (60, "12.00")},
        tiempo_atencion=20,
        condicion_pago_dias=0,
    )

    comparativo = await _comparativo(cliente, pedido)
    assert comparativo["cotizaciones"][0]["cotizacion_id"] == cot_bueno
    assert comparativo["cotizaciones"][0]["optimo"] is True
    assert comparativo["cotizaciones"][1]["optimo"] is False
    # Ganar los cuatro criterios es sacar los 100 puntos.
    assert Decimal(comparativo["cotizaciones"][0]["puntaje_total"]) == Decimal("100")


async def test_el_puntaje_total_es_la_suma_de_los_aportes(cliente, catalogo):
    """Lo que la pantalla muestra por criterio tiene que dar el total, o el
    cuadro no se puede auditar a mano."""
    producto = await _producto(cliente, catalogo, "CMP-031")
    pedido = await _pedido_con_lineas(cliente, catalogo, {producto: 100})
    uno = await _proveedor(cliente, "20100000032", "UNA S.A.C.")
    dos = await _proveedor(cliente, "20100000033", "OTRA S.A.C.")

    await _cotizacion_con_lineas(
        cliente, catalogo, pedido, uno, {producto: (100, "10.00")}, 5, 30
    )
    await _cotizacion_con_lineas(
        cliente, catalogo, pedido, dos, {producto: (80, "13.00")}, 9, 15
    )

    comparativo = await _comparativo(cliente, pedido)
    for fila in comparativo["cotizaciones"]:
        suma = sum(Decimal(c["aporte"]) for c in fila["criterios"].values())
        assert abs(suma - Decimal(fila["puntaje_total"])) <= Decimal("0.02")


async def test_dos_cotizaciones_identicas_empatan_como_optimas(cliente, catalogo):
    """Inventar un desempate escondería que el comparativo no las distingue."""
    producto = await _producto(cliente, catalogo, "CMP-032")
    pedido = await _pedido_con_lineas(cliente, catalogo, {producto: 100})
    uno = await _proveedor(cliente, "20100000034", "GEMELA UNO S.A.C.")
    dos = await _proveedor(cliente, "20100000035", "GEMELA DOS S.A.C.")

    for proveedor in (uno, dos):
        await _cotizacion_con_lineas(
            cliente, catalogo, pedido, proveedor, {producto: (100, "10.00")}, 5, 30
        )

    comparativo = await _comparativo(cliente, pedido)
    assert [c["optimo"] for c in comparativo["cotizaciones"]] == [True, True]


async def test_los_pesos_viajan_en_la_respuesta(cliente, catalogo):
    """La pantalla rotula las columnas con esto, en vez de repetir los números
    y quedar desincronizada si cambian."""
    producto = await _producto(cliente, catalogo, "CMP-033")
    pedido = await _pedido_con_lineas(cliente, catalogo, {producto: 10})
    proveedor = await _proveedor(cliente, "20100000036", "PESOS S.A.C.")
    await _cotizacion_con_lineas(
        cliente, catalogo, pedido, proveedor, {producto: (10, "5.00")}
    )

    assert (await _comparativo(cliente, pedido))["pesos"] == PESOS


# ============ Las rechazadas se listan pero no compiten ============


async def test_la_rechazada_se_lista_pero_no_puede_ser_optima(cliente, catalogo):
    """Se la muestra —el cuadro es el registro de contra qué se eligió— pero no
    se la sugiere: se la descartó por algo que los cuatro criterios no miden."""
    producto = await _producto(cliente, catalogo, "CMP-040")
    pedido = await _pedido_con_lineas(cliente, catalogo, {producto: 100})
    viva = await _proveedor(cliente, "20100000040", "VIVA S.A.C.")
    fuera = await _proveedor(cliente, "20100000041", "FUERA S.A.C.")

    cot_viva = await _cotizacion_con_lineas(
        cliente, catalogo, pedido, viva, {producto: (100, "10.00")}
    )
    # Diez veces más barata: ganaría el cuadro si se la dejara competir.
    cot_fuera = await _cotizacion_con_lineas(
        cliente, catalogo, pedido, fuera, {producto: (100, "1.00")}
    )
    await cliente.patch(
        f"{BASE}/cotizaciones/{cot_fuera}",
        json={"estado_id": await _estado(cliente, CODIGO_RECHAZADO)},
    )

    comparativo = await _comparativo(cliente, pedido)
    ids = {c["cotizacion_id"] for c in comparativo["cotizaciones"]}
    assert ids == {cot_viva, cot_fuera}
    assert _por_id(comparativo, cot_fuera)["optimo"] is False
    assert _por_id(comparativo, cot_viva)["optimo"] is True


async def test_si_todas_estan_rechazadas_ninguna_es_optima(cliente, catalogo):
    producto = await _producto(cliente, catalogo, "CMP-041")
    pedido = await _pedido_con_lineas(cliente, catalogo, {producto: 100})
    uno = await _proveedor(cliente, "20100000042", "UNA S.A.C.")
    dos = await _proveedor(cliente, "20100000043", "OTRA S.A.C.")

    for proveedor in (uno, dos):
        cot = await _cotizacion_con_lineas(
            cliente, catalogo, pedido, proveedor, {producto: (100, "10.00")}
        )
        await cliente.patch(
            f"{BASE}/cotizaciones/{cot}",
            json={"estado_id": await _estado(cliente, CODIGO_RECHAZADO)},
        )

    comparativo = await _comparativo(cliente, pedido)
    assert len(comparativo["cotizaciones"]) == 2
    assert not any(c["optimo"] for c in comparativo["cotizaciones"])


# ============ Aprobar una rechaza a las demás ============


async def test_aprobar_una_rechaza_a_las_hermanas(cliente, catalogo):
    """Elegir a un proveedor es no elegir a los otros.

    Sin esto quedaban varias cotizaciones aprobadas para el mismo pedido, cada
    una con su orden de compra, y el market comprometido a comprar lo mismo dos
    veces.
    """
    producto = await _producto(cliente, catalogo, "CMP-080")
    pedido = await _pedido_con_lineas(cliente, catalogo, {producto: 100})
    elegida = await _proveedor(cliente, "20100000080", "ELEGIDA S.A.C.")
    otra = await _proveedor(cliente, "20100000081", "OTRA S.A.C.")
    tercera = await _proveedor(cliente, "20100000082", "TERCERA S.A.C.")

    cot_elegida = await _cotizacion_con_lineas(
        cliente, catalogo, pedido, elegida, {producto: (100, "10.00")}
    )
    cot_otra = await _cotizacion_con_lineas(
        cliente, catalogo, pedido, otra, {producto: (100, "11.00")}
    )
    # Una observada también estaba en carrera, así que también se descarta.
    cot_tercera = await _cotizacion_con_lineas(
        cliente, catalogo, pedido, tercera, {producto: (100, "12.00")}
    )
    await cliente.patch(
        f"{BASE}/cotizaciones/{cot_tercera}",
        json={"estado_id": await _estado(cliente, CODIGO_OBSERVADO)},
    )

    r = await cliente.patch(
        f"{BASE}/cotizaciones/{cot_elegida}",
        json={"estado_id": await _estado(cliente, CODIGO_APROBADO)},
    )
    assert r.status_code == 200, r.text

    rechazado = await _estado(cliente, CODIGO_RECHAZADO)
    aprobado = await _estado(cliente, CODIGO_APROBADO)
    for cot_id, esperado in (
        (cot_elegida, aprobado),
        (cot_otra, rechazado),
        (cot_tercera, rechazado),
    ):
        actual = (await cliente.get(f"{BASE}/cotizaciones/{cot_id}")).json()
        assert actual["estado_id"] == esperado, cot_id


async def test_solo_se_rechazan_las_del_mismo_pedido(cliente, catalogo):
    """La regla es por pedido: aprobar una no puede tocar otra negociación."""
    producto = await _producto(cliente, catalogo, "CMP-081")
    pedido_a = await _pedido_con_lineas(cliente, catalogo, {producto: 100})
    pedido_b = await _pedido_con_lineas(cliente, catalogo, {producto: 100})
    uno = await _proveedor(cliente, "20100000083", "UNA S.A.C.")
    dos = await _proveedor(cliente, "20100000084", "OTRA S.A.C.")

    cot_a1 = await _cotizacion_con_lineas(
        cliente, catalogo, pedido_a, uno, {producto: (100, "10.00")}
    )
    await _cotizacion_con_lineas(
        cliente, catalogo, pedido_a, dos, {producto: (11, "11.00")}
    )
    cot_b1 = await _cotizacion_con_lineas(
        cliente, catalogo, pedido_b, uno, {producto: (100, "10.00")}
    )

    await cliente.patch(
        f"{BASE}/cotizaciones/{cot_a1}",
        json={"estado_id": await _estado(cliente, CODIGO_APROBADO)},
    )

    del_otro = (await cliente.get(f"{BASE}/cotizaciones/{cot_b1}")).json()
    assert del_otro["estado_id"] == await _estado(cliente, CODIGO_PENDIENTE)


async def test_no_se_rechaza_a_una_hermana_que_ya_estaba_aprobada(cliente, catalogo):
    """Tiene una orden de compra viva colgando.

    Solo pasa con datos anteriores a esta regla. Rechazarla dejaría el documento
    diciendo una cosa y su orden otra, así que se la deja como está y el
    desajuste queda a la vista en vez de taparse.
    """
    producto = await _producto(cliente, catalogo, "CMP-082")
    pedido = await _pedido_con_lineas(cliente, catalogo, {producto: 100})
    primera = await _proveedor(cliente, "20100000085", "PRIMERA S.A.C.")
    segunda = await _proveedor(cliente, "20100000086", "SEGUNDA S.A.C.")

    cot_primera = await _cotizacion_con_lineas(
        cliente, catalogo, pedido, primera, {producto: (100, "10.00")}
    )
    cot_segunda = await _cotizacion_con_lineas(
        cliente, catalogo, pedido, segunda, {producto: (100, "11.00")}
    )

    aprobado = await _estado(cliente, CODIGO_APROBADO)
    await cliente.patch(
        f"{BASE}/cotizaciones/{cot_primera}", json={"estado_id": aprobado}
    )
    # La segunda se aprueba a mano después: la primera ya está aprobada.
    await cliente.patch(
        f"{BASE}/cotizaciones/{cot_segunda}", json={"estado_id": aprobado}
    )

    quedo = (await cliente.get(f"{BASE}/cotizaciones/{cot_primera}")).json()
    assert quedo["estado_id"] == aprobado


async def test_reaprobar_no_vuelve_a_rechazar(cliente, catalogo):
    """El gancho cuelga de la primera aprobación.

    Si corriera en cada PATCH, observar una hermana después de haber elegido y
    volver a guardar la aprobada la rechazaría de nuevo, borrando una decisión
    posterior del usuario.
    """
    producto = await _producto(cliente, catalogo, "CMP-083")
    pedido = await _pedido_con_lineas(cliente, catalogo, {producto: 100})
    elegida = await _proveedor(cliente, "20100000087", "ELEGIDA S.A.C.")
    otra = await _proveedor(cliente, "20100000088", "OTRA S.A.C.")

    cot_elegida = await _cotizacion_con_lineas(
        cliente, catalogo, pedido, elegida, {producto: (100, "10.00")}
    )
    cot_otra = await _cotizacion_con_lineas(
        cliente, catalogo, pedido, otra, {producto: (100, "11.00")}
    )

    aprobado = await _estado(cliente, CODIGO_APROBADO)
    await cliente.patch(
        f"{BASE}/cotizaciones/{cot_elegida}", json={"estado_id": aprobado}
    )
    # El usuario reabre la descartada y la deja pendiente otra vez.
    pendiente = await _estado(cliente, CODIGO_PENDIENTE)
    await cliente.patch(
        f"{BASE}/cotizaciones/{cot_otra}", json={"estado_id": pendiente}
    )
    # Y toca la aprobada sin cambiarle el estado.
    await cliente.patch(
        f"{BASE}/cotizaciones/{cot_elegida}", json={"fecha": "2026-08-20"}
    )

    sigue = (await cliente.get(f"{BASE}/cotizaciones/{cot_otra}")).json()
    assert sigue["estado_id"] == pendiente


# ===================== Aprobar cualquiera, no solo la óptima =====================


async def test_se_puede_aprobar_una_que_no_es_la_optima(cliente, catalogo):
    """El óptimo es una sugerencia. Quien compra puede tener motivos que el
    cuadro no conoce, así que la decisión no se le quita."""
    producto = await _producto(cliente, catalogo, "CMP-050")
    pedido = await _pedido_con_lineas(cliente, catalogo, {producto: 100})
    mejor = await _proveedor(cliente, "20100000050", "MEJOR S.A.C.")
    peor = await _proveedor(cliente, "20100000051", "PEOR S.A.C.")

    await _cotizacion_con_lineas(
        cliente, catalogo, pedido, mejor, {producto: (100, "8.00")}, 2, 60
    )
    cot_peor = await _cotizacion_con_lineas(
        cliente, catalogo, pedido, peor, {producto: (100, "15.00")}, 20, 0
    )

    assert _por_id(await _comparativo(cliente, pedido), cot_peor)["optimo"] is False

    r = await cliente.patch(
        f"{BASE}/cotizaciones/{cot_peor}",
        json={"estado_id": await _estado(cliente, CODIGO_APROBADO)},
    )
    assert r.status_code == 200, r.text
    # Y aprobarla emite su orden de compra, como cualquier otra aprobación.
    ordenes = (
        await cliente.get(f"{BASE}/ordenes-compra", params={"cotizacion_id": cot_peor})
    ).json()["items"]
    assert len(ordenes) == 1


# ===================== Bordes =====================


async def test_pedido_sin_cotizaciones_devuelve_lista_vacia(cliente, catalogo):
    """Vacío y no 404: el pedido existe, todavía nadie cotizó."""
    producto = await _producto(cliente, catalogo, "CMP-060")
    pedido = await _pedido_con_lineas(cliente, catalogo, {producto: 10})

    comparativo = await _comparativo(cliente, pedido)
    assert comparativo["cotizaciones"] == []
    assert comparativo["unidades_pedidas"] == 10


async def test_pedido_que_no_existe_devuelve_400(cliente):
    r = await cliente.get(
        f"{BASE}/pedidos/11111111-1111-1111-1111-111111111111/comparativo-cotizaciones"
    )
    assert r.status_code == 400, r.text


async def test_la_cotizacion_sin_lineas_no_puede_ser_optima(cliente, catalogo):
    """No atiende nada, así que no tiene precio por unidad y pierde precio y
    stock: 55 de los 100 puntos. Con solo entrega y pago no alcanza."""
    producto = await _producto(cliente, catalogo, "CMP-061")
    pedido = await _pedido_con_lineas(cliente, catalogo, {producto: 100})
    real = await _proveedor(cliente, "20100000060", "REAL S.A.C.")
    vacia = await _proveedor(cliente, "20100000061", "VACIA S.A.C.")

    cot_real = await _cotizacion_con_lineas(
        cliente, catalogo, pedido, real, {producto: (100, "10.00")}, 10, 0
    )
    # Gana entrega y pago, pero no cotizó nada.
    cot_vacia = await _cotizacion_con_lineas(
        cliente, catalogo, pedido, vacia, {}, 0, 90
    )

    comparativo = await _comparativo(cliente, pedido)
    fila_vacia = _por_id(comparativo, cot_vacia)
    assert fila_vacia["precio_por_unidad"] is None
    assert fila_vacia["unidades_atendidas"] == 0
    assert fila_vacia["optimo"] is False
    assert _por_id(comparativo, cot_real)["optimo"] is True


# ===================== Entrada por el requerimiento =====================


async def test_el_comparativo_del_requerimiento_llega_al_mismo_cuadro(
    cliente, catalogo
):
    """Es la pregunta del usuario —"las cotizaciones de este requerimiento"—
    aunque las cotizaciones cuelguen del pedido."""
    producto = await _producto(cliente, catalogo, "CMP-070")
    almacen = await _almacen(cliente)
    req = (
        await cliente.post(
            f"{BASE}/requerimientos",
            json={
                "almacen_id": almacen,
                "estado_id": await _estado(cliente, CODIGO_PENDIENTE),
            },
        )
    ).json()["id"]
    r = await cliente.post(
        f"{BASE}/requerimientos-detalle",
        json={
            "requerimiento_id": req,
            "producto_id": producto,
            "unidad_medida_id": catalogo["unidad_compra"],
            "cantidad": 100,
        },
    )
    assert r.status_code == 201, r.text

    # Aprobarlo abre el pedido con la misma línea.
    await cliente.patch(
        f"{BASE}/requerimientos/{req}",
        json={"estado_id": await _estado(cliente, CODIGO_APROBADO)},
    )
    pedido = (
        await cliente.get(f"{BASE}/pedidos", params={"requerimiento_id": req})
    ).json()["items"][0]["id"]

    por_requerimiento = await cliente.get(
        f"{BASE}/requerimientos/{req}/comparativo-cotizaciones"
    )
    assert por_requerimiento.status_code == 200, por_requerimiento.text
    assert por_requerimiento.json()["pedido_id"] == pedido
    assert por_requerimiento.json()["requerimiento_id"] == req


async def test_requerimiento_sin_pedido_dice_que_hay_que_aprobarlo(cliente, catalogo):
    producto = await _producto(cliente, catalogo, "CMP-071")
    almacen = await _almacen(cliente)
    req = (
        await cliente.post(
            f"{BASE}/requerimientos",
            json={
                "almacen_id": almacen,
                "estado_id": await _estado(cliente, CODIGO_PENDIENTE),
            },
        )
    ).json()["id"]
    await cliente.post(
        f"{BASE}/requerimientos-detalle",
        json={
            "requerimiento_id": req,
            "producto_id": producto,
            "unidad_medida_id": catalogo["unidad_compra"],
            "cantidad": 10,
        },
    )

    r = await cliente.get(f"{BASE}/requerimientos/{req}/comparativo-cotizaciones")
    assert r.status_code == 400, r.text
    assert "pedido" in r.json()["detail"].lower()
