from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase


class ProveedorProductoBase(BaseModel):
    empresa_id: uuid.UUID
    producto_id: uuid.UUID
    #: Días desde que se hace el pedido hasta que el proveedor lo atiende.
    #: 0 es válido (entrega inmediata); negativo no tiene sentido.
    tiempo_atencion: int = Field(ge=0, le=365, description="Días de atención")


class ProveedorProductoCreate(ProveedorProductoBase):
    pass


class ProveedorProductoUpdate(BaseModel):
    """Actualización parcial: todo opcional.

    `tiempo_atencion` lleva `= None` explícito. Sin el default, Pydantic lo
    trata como obligatorio-que-admite-null: un PATCH que no lo enviara sería
    rechazado, y uno que enviara `null` intentaría dejar en NULL una columna
    que no lo admite.
    """

    empresa_id: uuid.UUID | None = None
    producto_id: uuid.UUID | None = None
    tiempo_atencion: int | None = Field(default=None, ge=0, le=365)


class ProveedorProductoResponse(RespuestaBase):
    empresa_id: uuid.UUID
    producto_id: uuid.UUID
    tiempo_atencion: int


class TiempoAtencionInput(BaseModel):
    """Cuerpo del PUT de asignación: solo el plazo.

    El producto no va acá porque ya viaja en la ruta. Tenerlo en los dos sitios
    permitiría mandar uno distinto al de la URL y que el servidor lo aceptara
    para después descartarlo, sin avisar de la contradicción.
    """

    tiempo_atencion: int = Field(ge=0, le=365, description="Días de atención")


class AsignacionProducto(BaseModel):
    """Una línea del alta masiva: qué producto y en cuántos días.

    Acá el `producto_id` sí es necesario: el POST masivo va a `/productos` sin
    id en la ruta, así que cada línea tiene que decir a qué producto se refiere.
    """

    producto_id: uuid.UUID
    tiempo_atencion: int = Field(ge=0, le=365)


class AsignarProductosInput(BaseModel):
    """Productos que distribuye un proveedor, en una sola operación."""

    asignaciones: list[AsignacionProducto] = Field(min_length=1)


class ProductoDelProveedor(BaseModel):
    """Lo que distribuye un proveedor, con el producto ya resuelto.

    Devuelve el SKU y la descripción además del id: quien consulta el catálogo
    de un proveedor necesita leerlo, no cruzar ids a mano.
    """

    model_config = RespuestaBase.model_config

    id: uuid.UUID
    producto_id: uuid.UUID
    sku: str
    descripcion_corta: str
    tiempo_atencion: int


class ProveedorDelProducto(BaseModel):
    """Quién provee un producto y en cuánto tiempo, para decidir a quién pedir."""

    model_config = RespuestaBase.model_config

    id: uuid.UUID
    empresa_id: uuid.UUID
    razon_social: str
    ruc: str
    tiempo_atencion: int
