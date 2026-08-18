"""Servicio de empresas, con la consulta de RUC contra decolecta.

La consulta externa sirve para dar de alta una empresa sin teclear la razón
social ni la dirección: se pide el RUC y el resto llega de SUNAT.

La condición de agente de retención/percepción **no** sale de acá: el
proveedor solo informa retención y nunca percepción, así que ese dato viene
del padrón oficial (`PadronAgentesService`).
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import requests

from app.core.config import settings
from app.core.crud import CRUDService
from app.core.exceptions import ConflictoError, ErrorDeDominio, NoEncontradoError
from app.modules.proveedores.models.empresa import Empresa
from app.modules.proveedores.schemas.empresa import EmpresaCreate

#: Segundos de espera. Sin tope, un cuelgue del proveedor deja la petición
#: colgada hasta que el cliente se rinde.
TIMEOUT_SEGUNDOS = 10

#: Longitud de un RUC peruano.
LARGO_RUC = 11


class ServicioExternoError(ErrorDeDominio):
    """La API de RUC no respondió o respondió algo inesperado. → 502"""


class ConsultaRucService:
    """Cliente de `GET {URL_API_RUC}?numero={ruc}` de decolecta.

    La URL y el token salen del `.env` (`URL_API_RUC` y `API_RUC_TOKEN`):
    nunca van en el código, que se versiona.
    """

    def __init__(self) -> None:
        self.url = settings.URL_API_RUC
        self.token = settings.API_RUC_TOKEN

    def _consultar_sincrono(self, ruc: str) -> dict[str, Any]:
        # El RUC va como parámetro y no concatenado: así la URL configurada es
        # una base normal y `requests` se encarga de escaparlo.
        respuesta = requests.get(
            self.url,
            params={"numero": ruc},
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            timeout=TIMEOUT_SEGUNDOS,
        )
        if respuesta.status_code == 404:
            raise NoEncontradoError("RUC", ruc)
        if respuesta.status_code in (401, 403):
            raise ServicioExternoError(
                "La API de RUC rechazó el token (revisar API_RUC_TOKEN en el .env)."
            )
        if not respuesta.ok:
            raise ServicioExternoError(
                f"La API de RUC respondió {respuesta.status_code}."
            )
        try:
            return respuesta.json()
        except ValueError as exc:
            raise ServicioExternoError(
                "La API de RUC devolvió una respuesta ilegible."
            ) from exc

    async def consultar(self, ruc: str) -> dict[str, Any]:
        """Datos de SUNAT para un RUC.

        `requests` es bloqueante y esta app es async: se ejecuta en un hilo
        aparte para no congelar el event loop mientras dura la llamada (y con
        ella, todas las demás peticiones del servidor).
        """
        ruc = (ruc or "").strip()
        if not ruc.isdigit() or len(ruc) != LARGO_RUC:
            raise ValueError(f"El RUC debe tener {LARGO_RUC} dígitos numéricos.")
        if not self.token or not self.url:
            raise ServicioExternoError(
                "Falta configurar URL_API_RUC y API_RUC_TOKEN en el .env."
            )

        try:
            return await asyncio.to_thread(self._consultar_sincrono, ruc)
        except requests.Timeout as exc:
            raise ServicioExternoError(
                f"La API de RUC no respondió en {TIMEOUT_SEGUNDOS} segundos."
            ) from exc
        except requests.RequestException as exc:
            raise ServicioExternoError("No se pudo contactar la API de RUC.") from exc


class EmpresaService(CRUDService[Empresa]):
    modelo = Empresa
    entidad = "Empresa"
    campos_unicos: ClassVar[dict[str, str | None]] = {"ruc": None}

    def __init__(self, db) -> None:  # type: ignore[no-untyped-def]
        super().__init__(db)
        self.consulta_ruc = ConsultaRucService()

    async def consultar_ruc(self, ruc: str) -> dict[str, Any]:
        """Datos crudos de SUNAT, normalizados a los campos de `Empresa`."""
        datos = await self.consulta_ruc.consultar(ruc)
        return self._normalizar(ruc, datos)

    async def crear_desde_ruc(self, ruc: str, es_proveedor: bool = True) -> Empresa:
        """Da de alta la empresa con lo que devuelve SUNAT.

        Si el RUC ya está registrado se corta antes de llamar a la API: no
        tiene sentido gastar una consulta externa para terminar en un 409.
        """
        existente = await self.buscar_por_ruc(ruc)
        if existente is not None:
            raise ConflictoError(f"Ya existe una empresa con el RUC {ruc}.")

        datos = await self.consultar_ruc(ruc)
        # La condición de agente sale del padrón oficial de SUNAT, no del
        # proveedor de consultas: decolecta solo informa retención y nunca
        # percepción. Si el padrón no se ha sincronizado la empresa queda como
        # no agente, y la próxima corrida del job la corrige.
        from app.modules.proveedores.services.padron_agentes import (
            PadronAgentesService,
        )

        es_ret, es_perc = await PadronAgentesService(self.db).es_agente(ruc)
        if not datos.get("ubigeo"):
            # La columna es obligatoria: sin ubigeo el INSERT fallaría con un
            # error de integridad en vez de un mensaje útil.
            raise ServicioExternoError(
                f"La API no devolvió el ubigeo del RUC {ruc}; no se puede dar de alta."
            )

        return await self.crear(
            EmpresaCreate(
                razon_social=datos["razon_social"],
                ruc=datos["numero_documento"],
                ubigeo_sunat=datos["ubigeo"],
                direccion=self._direccion_completa(datos),
                es_proveedor=es_proveedor,
                es_ag_retencion=es_ret,
                es_ag_percepcion=es_perc,
                estado=datos.get("estado"),
            )
        )

    async def buscar_por_ruc(self, ruc: str) -> Empresa | None:
        from sqlalchemy import select

        return (
            await self.db.execute(select(Empresa).where(Empresa.ruc == ruc.strip()))
        ).scalar_one_or_none()

    @staticmethod
    def _normalizar(ruc: str, datos: dict[str, Any]) -> dict[str, Any]:
        """Aplana la respuesta del proveedor a los campos que usa `Empresa`.

        Los nombres primeros son los de decolecta; los siguientes son los que
        usaba api.json.pe y los que suelen aparecer en proveedores parecidos.
        Mantenerlos cuesta nada y evita que un cambio de nombre deje el campo
        en `None` sin que nadie se entere.

        La condición de agente **no** sale de acá: decolecta solo informa
        retención (y como booleano), nunca percepción. Ese dato viene del
        padrón oficial, ver `PadronAgentesService`.
        """
        cuerpo = datos.get("data") if isinstance(datos.get("data"), dict) else datos

        def primero(*claves: str) -> str | None:
            for clave in claves:
                valor = cuerpo.get(clave)
                if isinstance(valor, str) and valor.strip():
                    return valor.strip()
            return None

        return {
            "numero_documento": primero("numero_documento", "ruc", "numeroDocumento")
            or ruc,
            "razon_social": primero(
                "razon_social", "nombre_o_razon_social", "razonSocial", "nombre"
            )
            or "",
            "direccion": primero("direccion", "direccion_completa", "domicilio_fiscal"),
            "distrito": primero("distrito"),
            "provincia": primero("provincia"),
            "departamento": primero("departamento"),
            "ubigeo": primero("ubigeo", "ubigeo_sunat"),
            "estado": primero("estado", "estado_contribuyente"),
            "condicion": primero("condicion", "condicion_domicilio"),
            "crudo": cuerpo,
        }

    #: La columna `direccion` es String(255): una dirección compuesta muy larga
    #: haría fallar la validación en medio de un alta que por lo demás es
    #: correcta, así que se recorta.
    LARGO_DIRECCION = 255

    @classmethod
    def _direccion_completa(cls, datos: dict[str, Any]) -> str | None:
        """Une calle, distrito, provincia y departamento en una sola línea.

        Se saltan las partes que el proveedor no devuelva: concatenarlas a pelo
        revienta con `TypeError` en cuanto una viene vacía, que es lo normal en
        los RUC con domicilio incompleto.
        """
        partes = (
            datos.get("direccion"),
            datos.get("distrito"),
            datos.get("provincia"),
            datos.get("departamento"),
        )
        limpias = [p.strip() for p in partes if isinstance(p, str) and p.strip()]
        return ", ".join(limpias)[: cls.LARGO_DIRECCION] or None
