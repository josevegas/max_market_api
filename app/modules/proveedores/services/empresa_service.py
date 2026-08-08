"""Servicio de empresas, con la consulta de RUC contra api.json.pe.

La consulta externa sirve para dar de alta una empresa sin teclear la razón
social ni la dirección: se pide el RUC y el resto llega de SUNAT.
"""

from __future__ import annotations

import asyncio
from typing import Any

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
    """Cliente de `POST {URL_API}ruc` de api.json.pe.

    La URL y el token salen del `.env` (`URL_API` y `API_JSON_TOKEN`): nunca
    van en el código, que se versiona.
    """

    def __init__(self) -> None:
        self.url = settings.URL_API.rstrip("/") + "/ruc"
        self.token = settings.API_JSON_TOKEN

    def _consultar_sincrono(self, ruc: str) -> dict[str, Any]:
        respuesta = requests.post(
            self.url,
            json={"ruc": ruc},
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
                "La API de RUC rechazó el token (revisar API_JSON_TOKEN en el .env)."
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
        if not self.token or not settings.URL_API:
            raise ServicioExternoError(
                "Falta configurar URL_API y API_JSON_TOKEN en el .env."
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
    campos_unicos = {"ruc": None}

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
        if not datos.get("ubigeo_sunat"):
            # La columna es obligatoria: sin ubigeo el INSERT fallaría con un
            # error de integridad en vez de un mensaje útil.
            raise ServicioExternoError(
                f"La API no devolvió el ubigeo del RUC {ruc}; no se puede dar de alta."
            )

        return await self.crear(
            EmpresaCreate(
                razon_social=datos["razon_social"],
                ruc=datos["ruc"],
                ubigeo_sunat=datos["ubigeo_sunat"],
                direccion=datos.get("direccion_completa"),
                es_proveedor=es_proveedor,
                es_ag_retencion=self._es_si(datos.get("es_agente_de_retencion")),
                es_ag_percepcion=self._es_si(datos.get("es_agente_de_percepcion")),
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
        """Aplana la respuesta de la API a los campos que usa `Empresa`.

        El proveedor no garantiza una forma fija (a veces envuelve el resultado
        en `data`), así que se busca por varios nombres posibles en lugar de
        confiar en uno solo. Los indicadores de agente vienen como "SI"/"NO",
        no como booleanos: se conservan tal cual en la respuesta y se
        convierten al crear la empresa.
        """
        cuerpo = datos.get("data") if isinstance(datos.get("data"), dict) else datos

        def primero(*claves: str) -> str | None:
            for clave in claves:
                valor = cuerpo.get(clave)
                if isinstance(valor, str) and valor.strip():
                    return valor.strip()
            return None

        return {
            "ruc": primero("ruc", "numeroDocumento") or ruc,
            "razon_social": primero(
                "nombre_o_razon_social", "razon_social", "razonSocial", "nombre"
            )
            or "",
            "direccion_completa": primero(
                "direccion_completa", "direccion", "domicilio_fiscal"
            ),
            "ubigeo_sunat": primero("ubigeo_sunat", "ubigeo"),
            "es_agente_de_retencion": primero("es_agente_de_retencion"),
            "es_agente_de_percepcion": primero("es_agente_de_percepcion"),
            "estado": primero("estado", "estado_contribuyente"),
            "condicion": primero("condicion", "condicion_domicilio"),
            "crudo": cuerpo,
        }

    @staticmethod
    def _es_si(valor: str | None) -> bool:
        """SUNAT responde "SI"/"NO" en los indicadores de agente."""
        return (valor or "").strip().upper() == "SI"
