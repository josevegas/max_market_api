"""Sincronización de los padrones de agentes de retención y percepción.

SUNAT publica dos ZIP con los agentes vigentes. Se descargan, se vuelcan a
`padron_agentes` reemplazando lo anterior y se reconcilia `empresas` para que
`es_ag_retencion` / `es_ag_percepcion` reflejen el padrón: eso corrige tanto las
altas como las **exclusiones**, que es lo que una comprobación puramente
aditiva nunca vería.

El parseo no usa `csv` ni pandas a propósito. Los archivos traen razones
sociales con comillas sueltas (`"AGROINVERSIONES ... E.I.R.L."`) que hacen que
un lector con semántica de comillas fusione líneas o falle; partir por `|` y
quedarse con la primera columna es inmune a eso, y el RUC es lo único que se
necesita.
"""

from __future__ import annotations

import asyncio
import io
import zipfile
from dataclasses import dataclass
from datetime import date, datetime

import requests
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ErrorDeDominio
from app.modules.proveedores.models.padron_agente import (
    TIPO_PERCEPCION,
    TIPO_RETENCION,
    PadronAgente,
    PadronSincronizacion,
)

#: Sin tope, un cuelgue de SUNAT deja la tarea colgada indefinidamente.
TIMEOUT_SEGUNDOS = 60

#: SUNAT devuelve 403 a los clientes que no parecen un navegador.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

#: Mínimo de filas por padrón para dar la descarga por buena. Los padrones
#: reales rondan las 7.200 y 550 filas; si llega mucho menos es que SUNAT
#: sirvió una página de error o un ZIP recortado, y reemplazar la tabla con eso
#: dejaría a media empresa marcada como no agente.
MINIMO_FILAS = {TIPO_RETENCION: 1_000, TIPO_PERCEPCION: 100}

LARGO_RUC = 11


class PadronError(ErrorDeDominio):
    """El padrón no se pudo descargar o vino inservible. → 502"""


@dataclass(frozen=True)
class FilaPadron:
    ruc: str
    a_partir_de: date | None
    resolucion: str | None


@dataclass(frozen=True)
class ResumenSincronizacion:
    ok: bool
    filas_retencion: int
    filas_percepcion: int
    empresas_actualizadas: int
    detalle: str | None = None


def _url_de(tipo: str) -> str:
    return (
        settings.URL_PADRON_RETENCION
        if tipo == TIPO_RETENCION
        else settings.URL_PADRON_PERCEPCION
    )


def _a_fecha(valor: str) -> date | None:
    """ "A partir del" viene como dd/mm/aaaa; si no se entiende, se deja vacío."""
    try:
        # DTZ007: es una fecha de calendario (dd/mm/aaaa), no un instante;
        # el huso no aplica y por eso se descarta con .date().
        return datetime.strptime(valor.strip(), "%d/%m/%Y").date()  # noqa: DTZ007
    except (ValueError, AttributeError):
        return None


def descargar_padron(tipo: str) -> list[FilaPadron]:
    """Descarga y parsea un padrón. Bloqueante: va en un hilo aparte.

    Formato real: ZIP con un único TXT en latin-1, cabecera
    `Ruc|Nombre/Razon|A partir del|Resolucion|` y un `|` final que produce una
    quinta columna vacía.
    """
    url = _url_de(tipo)
    try:
        respuesta = requests.get(url, headers=HEADERS, timeout=TIMEOUT_SEGUNDOS)
    except requests.Timeout as exc:
        raise PadronError(
            f"El padrón de {tipo} no respondió en {TIMEOUT_SEGUNDOS} segundos."
        ) from exc
    except requests.RequestException as exc:
        raise PadronError(f"No se pudo contactar el padrón de {tipo}.") from exc

    if respuesta.status_code == 403:
        raise PadronError(
            f"SUNAT rechazó la descarga del padrón de {tipo} con un 403 "
            "(suele ser el User-Agent)."
        )
    if not respuesta.ok:
        raise PadronError(f"El padrón de {tipo} respondió {respuesta.status_code}.")

    try:
        with zipfile.ZipFile(io.BytesIO(respuesta.content)) as z:
            txts = [n for n in z.namelist() if n.lower().endswith(".txt")]
            if not txts:
                raise PadronError(
                    f"El ZIP del padrón de {tipo} no trae ningún .txt "
                    f"(contiene: {z.namelist()})."
                )
            contenido = z.open(txts[0]).read().decode("latin-1")
    except zipfile.BadZipFile as exc:
        raise PadronError(
            f"Lo que devolvió el padrón de {tipo} no es un ZIP válido."
        ) from exc

    filas: list[FilaPadron] = []
    vistos: set[str] = set()
    for linea in contenido.splitlines()[1:]:  # [1:] salta la cabecera
        if not linea.strip():
            continue
        campos = linea.split("|")
        ruc = campos[0].strip()
        # Las líneas que no empiezan por un RUC son basura del archivo (o una
        # razón social partida en dos por un salto de línea): se descartan.
        if len(ruc) != LARGO_RUC or not ruc.isdigit() or ruc in vistos:
            continue
        vistos.add(ruc)
        filas.append(
            FilaPadron(
                ruc=ruc,
                a_partir_de=_a_fecha(campos[2]) if len(campos) > 2 else None,
                resolucion=(campos[3].strip()[:60] or None)
                if len(campos) > 3
                else None,
            )
        )

    minimo = MINIMO_FILAS[tipo]
    if len(filas) < minimo:
        raise PadronError(
            f"El padrón de {tipo} trajo solo {len(filas)} filas válidas "
            f"(se esperaban al menos {minimo}). No se reemplaza el padrón "
            "guardado para no perder los datos buenos."
        )
    return filas


class PadronAgentesService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Consulta ────────────────────────────────────────────────────────────

    async def es_agente(self, ruc: str) -> tuple[bool, bool]:
        """`(es_ag_retencion, es_ag_percepcion)` según el padrón local."""
        ruc = (ruc or "").strip()
        tipos = (
            (
                await self.db.execute(
                    select(PadronAgente.tipo).where(PadronAgente.ruc == ruc)
                )
            )
            .scalars()
            .all()
        )
        return TIPO_RETENCION in tipos, TIPO_PERCEPCION in tipos

    async def esta_vacio(self) -> bool:
        total = await self.db.scalar(select(func.count()).select_from(PadronAgente))
        return not total

    async def ultima_sincronizacion(self) -> PadronSincronizacion | None:
        return (
            await self.db.execute(
                select(PadronSincronizacion)
                .order_by(PadronSincronizacion.ejecutada_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def conteos(self) -> dict[str, int]:
        filas = await self.db.execute(
            select(PadronAgente.tipo, func.count()).group_by(PadronAgente.tipo)
        )
        # `.all()` y no `dict(filas)` directo: un `Result` tiene `.keys()`, así
        # que `dict()` lo toma por un mapping e intenta indexarlo.
        return dict(filas.all())

    # ── Sincronización ──────────────────────────────────────────────────────

    async def sincronizar(self) -> ResumenSincronizacion:
        """Descarga ambos padrones, los vuelca y reconcilia las empresas.

        Las descargas van primero y fuera de la transacción de escritura: si
        SUNAT falla, la tabla se queda como estaba y solo se registra el
        intento fallido.
        """
        try:
            # `requests` es bloqueante y esto corre en un event loop: sin el
            # hilo aparte se congelarían todas las demás peticiones durante la
            # descarga.
            retencion, percepcion = await asyncio.gather(
                asyncio.to_thread(descargar_padron, TIPO_RETENCION),
                asyncio.to_thread(descargar_padron, TIPO_PERCEPCION),
            )
        except PadronError as exc:
            await self._registrar(ResumenSincronizacion(False, 0, 0, 0, str(exc)))
            raise

        await self.db.execute(delete(PadronAgente))
        self.db.add_all(
            [
                PadronAgente(
                    ruc=f.ruc,
                    tipo=tipo,
                    a_partir_de=f.a_partir_de,
                    resolucion=f.resolucion,
                )
                for tipo, filas in (
                    (TIPO_RETENCION, retencion),
                    (TIPO_PERCEPCION, percepcion),
                )
                for f in filas
            ]
        )
        await self.db.flush()

        actualizadas = await self.reconciliar_empresas()

        resumen = ResumenSincronizacion(
            ok=True,
            filas_retencion=len(retencion),
            filas_percepcion=len(percepcion),
            empresas_actualizadas=actualizadas,
        )
        await self._registrar(resumen)
        return resumen

    async def reconciliar_empresas(self) -> int:
        """Alinea `es_ag_retencion`/`es_ag_percepcion` con el padrón.

        Un solo UPDATE por columna, y solo sobre las filas que cambian, para
        que el contador refleje cambios reales y no toda la tabla.
        """
        total = 0
        for columna, tipo in (
            ("es_ag_retencion", TIPO_RETENCION),
            ("es_ag_percepcion", TIPO_PERCEPCION),
        ):
            resultado = await self.db.execute(
                text(
                    f"""
                    UPDATE empresas e
                       SET {columna} = p.esta
                      FROM (
                            SELECT e2.id,
                                   EXISTS (
                                       SELECT 1 FROM padron_agentes pa
                                        WHERE pa.ruc = e2.ruc AND pa.tipo = :tipo
                                   ) AS esta
                              FROM empresas e2
                           ) p
                     WHERE e.id = p.id AND e.{columna} IS DISTINCT FROM p.esta
                    """
                ),
                {"tipo": tipo},
            )
            total += resultado.rowcount or 0
        return total

    async def _registrar(self, resumen: ResumenSincronizacion) -> None:
        self.db.add(
            PadronSincronizacion(
                ok=resumen.ok,
                filas_retencion=resumen.filas_retencion,
                filas_percepcion=resumen.filas_percepcion,
                empresas_actualizadas=resumen.empresas_actualizadas,
                detalle=resumen.detalle,
            )
        )
        await self.db.commit()
