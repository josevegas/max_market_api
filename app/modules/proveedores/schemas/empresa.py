from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

LARGO_RUC = 11


class EmpresaBase(BaseModel):
    razon_social: str = Field(min_length=1, max_length=100)
    ruc: str = Field(min_length=LARGO_RUC, max_length=LARGO_RUC)
    #: Código de ubigeo de SUNAT (6 dígitos). Obligatorio en el modelo.
    ubigeo_sunat: str = Field(min_length=6, max_length=6)
    direccion: str | None = Field(default=None, max_length=255)
    telefono: str | None = Field(default=None, max_length=20)
    #: Estado de contribuyente de SUNAT. Obligatorio en el modelo.
    estado: str = Field(min_length=1, max_length=30)
    email: str | None = Field(default=None, max_length=100)
    es_proveedor: bool = False
    es_ag_retencion: bool = False
    es_ag_percepcion: bool = False

    @field_validator("ruc")
    @classmethod
    def _ruc_numerico(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit():
            raise ValueError(f"El RUC debe tener {LARGO_RUC} dígitos numéricos.")
        return v


class EmpresaCreate(EmpresaBase):
    pass


class EmpresaUpdate(BaseModel):
    razon_social: str | None = Field(default=None, min_length=1, max_length=100)
    ruc: str | None = Field(default=None, min_length=LARGO_RUC, max_length=LARGO_RUC)
    ubigeo_sunat: str | None = Field(default=None, min_length=6, max_length=6)
    direccion: str | None = Field(default=None, max_length=255)
    telefono: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=100)
    es_proveedor: bool | None = None
    es_ag_retencion: bool | None = None
    es_ag_percepcion: bool | None = None


class EmpresaResponse(EmpresaBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: uuid.UUID | None = None
    updated_by: uuid.UUID | None = None


class ConsultaRucInput(BaseModel):
    """RUC a consultar en SUNAT."""

    ruc: str = Field(
        min_length=LARGO_RUC, max_length=LARGO_RUC, examples=["20552103816"]
    )


class ConsultaRucResponse(BaseModel):
    """Datos de SUNAT ya normalizados a los campos de `Empresa`.

    `crudo` va incluido para no perder lo que devuelve el proveedor: su
    respuesta no tiene una forma fija y ahí queda todo lo que no se mapeó.
    """

    numero_documento: str
    razon_social: str
    direccion: str | None = None
    distrito: str | None = None
    provincia: str | None = None
    departamento: str | None = None
    ubigeo: str | None = None
    estado: str | None = None
    condicion: str | None = None
    crudo: dict = Field(default_factory=dict)
