from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.shared.base import RespuestaBase, rechazar_nulos


class GuiaRemisionDetalleCreate(BaseModel):
    guia_remision_id: uuid.UUID
    producto_id: uuid.UUID
    unidad_medida_id: uuid.UUID
    #: `ge` y no `min`: `min` no existe en Pydantic v2, se acepta en silencio y
    #: no valida nada (un -5 pasaba). Se admite 0 para poder registrar una
    #: línea que el proveedor no llegó a entregar.
    cantidad: int = Field(default=0, ge=0)


class GuiaRemisionDetalleUpdate(BaseModel):
    """Actualización parcial: todo opcional."""

    guia_remision_id: uuid.UUID | None = None
    producto_id: uuid.UUID | None = None
    unidad_medida_id: uuid.UUID | None = None
    # El tipo lleva `| None`: declarado como `int` con default `None` mentía
    # sobre lo que admite, y un null daba un error poco claro.
    cantidad: int | None = Field(default=None, ge=0)

    _no_nulos = rechazar_nulos(
        "guia_remision_id", "producto_id", "unidad_medida_id", "cantidad"
    )


class GuiaRemisionDetalleResponse(RespuestaBase):
    guia_remision_id: uuid.UUID
    producto_id: uuid.UUID
    unidad_medida_id: uuid.UUID
    cantidad: int
