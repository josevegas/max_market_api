from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.modules.productos.schemas.base import RespuestaBase


class ProductoCreate(BaseModel):
    tipo_producto: str = Field(min_length=1, max_length=20)
    #: Único: es el identificador con el que opera el negocio.
    sku: str = Field(min_length=1, max_length=15)
    codigo_barras: str | None = Field(default=None, max_length=50)

    # Descripciones, cada una para un documento distinto.
    descripcion_corta: str = Field(min_length=1, max_length=32)
    descripcion_legal: str = Field(min_length=1, max_length=100)
    descripcion_compra: str = Field(min_length=1, max_length=100)
    descripcion_web: str = Field(min_length=1, max_length=100)

    familia_id: uuid.UUID
    sub_familia_id: uuid.UUID
    categoria_id: uuid.UUID
    #: Opcionales, igual que en el modelo.
    sub_categoria_id: uuid.UUID | None = None
    presentacion_id: uuid.UUID | None = None


class ProductoUpdate(BaseModel):
    tipo_producto: str | None = Field(default=None, min_length=1, max_length=20)
    sku: str | None = Field(default=None, min_length=1, max_length=15)
    codigo_barras: str | None = Field(default=None, max_length=50)
    descripcion_corta: str | None = Field(default=None, min_length=1, max_length=32)
    descripcion_legal: str | None = Field(default=None, min_length=1, max_length=100)
    descripcion_compra: str | None = Field(default=None, min_length=1, max_length=100)
    descripcion_web: str | None = Field(default=None, min_length=1, max_length=100)
    familia_id: uuid.UUID | None = None
    sub_familia_id: uuid.UUID | None = None
    categoria_id: uuid.UUID | None = None
    sub_categoria_id: uuid.UUID | None = None
    presentacion_id: uuid.UUID | None = None


class ProductoResponse(RespuestaBase):
    tipo_producto: str
    sku: str
    codigo_barras: str | None = None
    descripcion_corta: str
    descripcion_legal: str
    descripcion_compra: str
    descripcion_web: str
    familia_id: uuid.UUID
    sub_familia_id: uuid.UUID
    categoria_id: uuid.UUID
    sub_categoria_id: uuid.UUID | None = None
    presentacion_id: uuid.UUID | None = None
