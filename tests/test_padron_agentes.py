"""Padrón de agentes de retención y percepción.

Los tests no salen a internet: se arma un ZIP en memoria con el mismo formato
que publica SUNAT (cabecera, `|` final, latin-1) y se sustituye `requests.get`.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from sqlalchemy import select, text

from app.db.session import AsyncSessionLocal
from app.modules.proveedores.models.padron_agente import (
    TIPO_PERCEPCION,
    TIPO_RETENCION,
    PadronAgente,
)
from app.modules.proveedores.services import padron_agentes as modulo
from app.modules.proveedores.services.padron_agentes import (
    PadronAgentesService,
    PadronError,
    descargar_padron,
)

CABECERA = "Ruc|Nombre/Razon|A partir del|Resolucion|"


def _zip_con(lineas: list[str]) -> bytes:
    """ZIP con un TXT en latin-1, como el de SUNAT."""
    contenido = "\r\n".join([CABECERA, *lineas]).encode("latin-1")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("AgenRet_TXT.txt", contenido)
    return buffer.getvalue()


def _filas(cantidad: int, inicio: int = 20100000001) -> list[str]:
    return [
        f"{inicio + i}|EMPRESA {i} S.A.C.|01/01/2025|RS R.S.229-2024|"
        for i in range(cantidad)
    ]


class _Respuesta:
    def __init__(self, contenido: bytes, status_code: int = 200) -> None:
        self.content = contenido
        self.status_code = status_code
        self.ok = 200 <= status_code < 300


@pytest.fixture
def sunat(monkeypatch):
    """Sustituye la descarga. Devuelve un setter para fijar la respuesta."""

    estado: dict = {}

    def _get(url, **kwargs):
        return estado["respuesta"]

    monkeypatch.setattr(modulo.requests, "get", _get)
    return lambda respuesta: estado.update(respuesta=respuesta)


# ===================== Parseo =====================


def test_la_cabecera_no_se_ingesta_como_dato(sunat):
    sunat(_Respuesta(_zip_con(_filas(1200))))

    filas = descargar_padron(TIPO_RETENCION)

    assert len(filas) == 1200
    assert all(f.ruc.isdigit() for f in filas)
    assert "Ruc" not in [f.ruc for f in filas]


def test_se_parsean_fecha_y_resolucion(sunat):
    sunat(_Respuesta(_zip_con(_filas(1200))))

    primera = descargar_padron(TIPO_RETENCION)[0]

    assert primera.a_partir_de.isoformat() == "2025-01-01"
    assert primera.resolucion == "RS R.S.229-2024"


def test_se_descartan_rucs_invalidos_y_duplicados(sunat):
    validas = _filas(1200)
    sucias = [
        "no-es-un-ruc|BASURA|01/01/2025|RS|",
        "123|CORTO|01/01/2025|RS|",
        validas[0],  # duplicado exacto
        "",
    ]
    sunat(_Respuesta(_zip_con(validas + sucias)))

    filas = descargar_padron(TIPO_RETENCION)

    assert len(filas) == 1200
    assert len({f.ruc for f in filas}) == 1200


def test_razon_social_con_comillas_no_rompe_el_parseo(sunat):
    """El lector `csv` de la stdlib falla con estas líneas; el split no."""
    con_comillas = ['20605059849|"AGROINVERSIONES MUNOZ E.I.R.L."|01/01/2025|RS|']
    sunat(_Respuesta(_zip_con(_filas(1200) + con_comillas)))

    filas = descargar_padron(TIPO_RETENCION)

    assert len(filas) == 1201
    assert "20605059849" in {f.ruc for f in filas}


# ===================== Guardas =====================


def test_un_padron_corto_no_reemplaza_nada(sunat):
    """Si SUNAT sirve un ZIP recortado, se aborta en vez de vaciar la tabla."""
    sunat(_Respuesta(_zip_con(_filas(10))))

    with pytest.raises(PadronError, match="al menos"):
        descargar_padron(TIPO_RETENCION)


def test_un_403_se_explica(sunat):
    sunat(_Respuesta(b"", status_code=403))

    with pytest.raises(PadronError, match="403"):
        descargar_padron(TIPO_RETENCION)


def test_un_zip_invalido_se_explica(sunat):
    sunat(_Respuesta(b"esto no es un zip"))

    with pytest.raises(PadronError, match="ZIP"):
        descargar_padron(TIPO_RETENCION)


def test_un_zip_sin_txt_se_explica(sunat):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("lo_que_sea.pdf", b"x")
    sunat(_Respuesta(buffer.getvalue()))

    with pytest.raises(PadronError, match="no trae ningún"):
        descargar_padron(TIPO_RETENCION)


# ===================== Reconciliación =====================


async def _crear_empresa(cliente, ruc: str, **extra) -> str:
    datos = {
        "razon_social": f"EMPRESA {ruc}",
        "ruc": ruc,
        "ubigeo_sunat": "150101",
        "estado": "ACTIVO",
        "es_proveedor": True,
        **extra,
    }
    r = await cliente.post("/api/v1/empresas", json=datos)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_reconciliar_marca_y_desmarca(cliente):
    """Lo importante: una empresa excluida del padrón debe quedar en falso."""
    en_padron = "20100000001"
    fuera = "20100000002"
    await _crear_empresa(cliente, en_padron)
    # Ya venía marcada, pero SUNAT la excluyó del padrón.
    await _crear_empresa(cliente, fuera, es_ag_retencion=True)

    async with AsyncSessionLocal() as db:
        db.add(PadronAgente(ruc=en_padron, tipo=TIPO_RETENCION))
        await db.flush()
        actualizadas = await PadronAgentesService(db).reconciliar_empresas()
        await db.commit()

        filas = dict(
            (await db.execute(text("SELECT ruc, es_ag_retencion FROM empresas"))).all()
        )

    assert filas[en_padron] is True
    assert filas[fuera] is False
    assert actualizadas == 2


async def test_reconciliar_no_cuenta_lo_que_no_cambia(cliente):
    await _crear_empresa(cliente, "20100000003")

    async with AsyncSessionLocal() as db:
        servicio = PadronAgentesService(db)
        assert await servicio.reconciliar_empresas() == 0
        await db.commit()


async def test_es_agente_distingue_los_dos_padrones(cliente):
    ruc = "20100000004"

    async with AsyncSessionLocal() as db:
        db.add(PadronAgente(ruc=ruc, tipo=TIPO_PERCEPCION))
        await db.commit()

        ret, perc = await PadronAgentesService(db).es_agente(ruc)

    assert ret is False
    assert perc is True


# ===================== Sincronización completa =====================


async def test_sincronizar_reemplaza_el_padron_y_registra_la_corrida(cliente, sunat):
    sunat(_Respuesta(_zip_con(_filas(1200))))

    async with AsyncSessionLocal() as db:
        # Una fila vieja que ya no está en el padrón nuevo debe desaparecer.
        db.add(PadronAgente(ruc="20999999999", tipo=TIPO_RETENCION))
        await db.commit()

        resumen = await PadronAgentesService(db).sincronizar()

        rucs = set((await db.execute(select(PadronAgente.ruc))).scalars().all())

    assert resumen.ok
    assert resumen.filas_retencion == 1200
    assert "20999999999" not in rucs

    r = await cliente.get("/api/v1/padron-agentes/estado")
    assert r.status_code == 200
    assert r.json()["tiene_datos"] is True
    assert r.json()["ultima_ok"] is True


async def test_una_descarga_fallida_deja_el_padron_intacto(cliente, sunat):
    async with AsyncSessionLocal() as db:
        db.add(PadronAgente(ruc="20888888888", tipo=TIPO_RETENCION))
        await db.commit()

    sunat(_Respuesta(_zip_con(_filas(5))))  # por debajo del mínimo

    async with AsyncSessionLocal() as db:
        with pytest.raises(PadronError):
            await PadronAgentesService(db).sincronizar()

    async with AsyncSessionLocal() as db:
        rucs = set((await db.execute(select(PadronAgente.ruc))).scalars().all())

    assert "20888888888" in rucs

    # El intento fallido queda registrado con su motivo.
    r = await cliente.get("/api/v1/padron-agentes/estado")
    assert r.json()["ultima_ok"] is False
    assert "al menos" in r.json()["ultimo_detalle"]
