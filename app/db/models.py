"""Registro central de modelos.

Alembic solo detecta lo que esté cargado en `Base.metadata`, y los modelos se
registran al importarse. Cada modelo nuevo se agrega acá; si no, `--autogenerate`
lo ignora en silencio y, peor, propone borrar sus tablas.

    from app.modules.productos.models.producto import Producto  # noqa: F401
"""

from __future__ import annotations

from app.db.base import Base  # noqa: F401

__all__ = ["Base"]
