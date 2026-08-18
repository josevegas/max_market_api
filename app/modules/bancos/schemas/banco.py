from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.shared.base import RespuestaBase, rechazar_nulos

LARGO_RUC = 11


def _validar_ruc(v: str | None) -> str | None:
    """Mismo criterio que `Empresa`: 11 dígitos y nada más."""
    if v is None:
        return None
    v = v.strip()
    if not v.isdigit():
        raise ValueError(f"El RUC debe tener {LARGO_RUC} dígitos numéricos.")
    return v


class BancoCreate(BaseModel):
    razon_social: str = Field(min_length=1, max_length=100)
    ruc: str = Field(min_length=LARGO_RUC, max_length=LARGO_RUC)
    # Los opcionales llevan `= None`: sin el default habría que enviarlos
    # explícitamente como null para poder crear un banco.
    direccion: str | None = Field(default=None, max_length=255)
    telefono: str | None = Field(default=None, max_length=15)
    codigo: str | None = Field(default=None, max_length=10)

    @field_validator("ruc")
    @classmethod
    def _ruc_numerico(cls, v: str) -> str:
        return _validar_ruc(v)  # type: ignore[return-value]


class BancoUpdate(BaseModel):
    """Actualización parcial: todo opcional (ver `ZonaUpdate` en markets)."""

    razon_social: str | None = Field(default=None, min_length=1, max_length=100)
    ruc: str | None = Field(default=None, min_length=LARGO_RUC, max_length=LARGO_RUC)
    direccion: str | None = Field(default=None, max_length=255)
    telefono: str | None = Field(default=None, max_length=15)
    codigo: str | None = Field(default=None, max_length=10)

    @field_validator("ruc")
    @classmethod
    def _ruc_numerico(cls, v: str | None) -> str | None:
        return _validar_ruc(v)

    # Columnas NOT NULL: omitirlas es válido, mandarlas como null no.
    _no_nulos = rechazar_nulos("razon_social", "ruc")


class BancoResponse(RespuestaBase):
    razon_social: str
    ruc: str
    direccion: str | None = None
    telefono: str | None = None
    codigo: str | None = None
