from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ResumenSincronizacionResponse(BaseModel):
    """Qué hizo la última corrida."""

    ok: bool
    filas_retencion: int
    filas_percepcion: int
    #: Empresas cuya condición de agente cambió al reconciliar.
    empresas_actualizadas: int
    detalle: str | None = None


class EstadoPadronResponse(BaseModel):
    """Para responder "¿cuándo se verificó esto por última vez?"."""

    #: Falso mientras nunca se haya sincronizado: en ese estado toda empresa
    #: nueva se registra como no agente.
    tiene_datos: bool
    agentes_retencion: int
    agentes_percepcion: int
    ultima_sincronizacion: datetime | None = None
    ultima_ok: bool | None = None
    ultimo_detalle: str | None = None
