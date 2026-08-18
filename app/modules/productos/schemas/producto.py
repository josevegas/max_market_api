from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase, rechazar_nulos


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
    #: Opcional, igual que en el modelo.
    sub_categoria_id: uuid.UUID | None = None
    #: Obligatoria: la columna es NOT NULL. Sin esto el fallo llega como un
    #: 400 de integridad en vez de un 422 que diga qué campo falta.
    presentacion_id: uuid.UUID
    #: Opcional: hay productos a granel y de marca propia que no tienen una.
    marca_fabricante: str | None = Field(default=None, max_length=25)
    #: Obligatorias, como la columna: el proveedor factura en una unidad y el
    #: market vende en otra, y sin las dos no hay contra qué convertir.
    unidad_venta: uuid.UUID
    unidad_compra: uuid.UUID


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
    marca_fabricante: str | None = Field(default=None, max_length=25)
    unidad_venta: uuid.UUID | None = None
    unidad_compra: uuid.UUID | None = None

    # Sus columnas son NOT NULL: mandarlas en null en un PATCH salía como un
    # 400 de integridad sin decir qué campo fue. `marca_fabricante` queda
    # fuera a propósito, que sí admite null y así se le quita la marca.
    _no_nulos = rechazar_nulos("unidad_venta", "unidad_compra")


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
    codigo_sunat: str | None = None
    marca_fabricante: str | None = None
    unidad_venta: uuid.UUID
    unidad_compra: uuid.UUID
