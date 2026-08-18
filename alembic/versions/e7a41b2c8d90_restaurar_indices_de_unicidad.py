"""restaurar índices de unicidad

`3c65ed377fab` los borró sin querer: son índices **funcionales**
(`lower(trim(...))`) creados con SQL suelto, así que no viven en
`Base.metadata` y `--autogenerate` los interpretó como sobrantes.

Esta migración los repone. Para que no vuelva a ocurrir, `alembic/env.py`
excluye del autogenerado los índices `uq_*`: quedan bajo control exclusivo de
las migraciones que los crean.

Revision ID: e7a41b2c8d90
Revises: df3b8a0d4e0d
Create Date: 2026-08-07 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "e7a41b2c8d90"
down_revision: str | None = "df3b8a0d4e0d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: (índice, tabla, expresión, condición parcial)
INDICES = [
    ("uq_familias_nombre", "familias", "lower(trim(nombre))", None),
    ("uq_familias_codigo", "familias", "lower(trim(codigo))", "codigo IS NOT NULL"),
    (
        "uq_sub_familias_familia_nombre",
        "sub_familias",
        "familia_id, lower(trim(nombre))",
        None,
    ),
    (
        "uq_sub_familias_codigo",
        "sub_familias",
        "lower(trim(codigo))",
        "codigo IS NOT NULL",
    ),
    (
        "uq_categorias_sub_familia_nombre",
        "categorias",
        "sub_familia_id, lower(trim(nombre))",
        None,
    ),
    ("uq_categorias_codigo", "categorias", "lower(trim(codigo))", "codigo IS NOT NULL"),
    (
        "uq_sub_categorias_categoria_nombre",
        "sub_categorias",
        "categoria_id, lower(trim(nombre))",
        None,
    ),
    (
        "uq_sub_categorias_codigo",
        "sub_categorias",
        "lower(trim(codigo))",
        "codigo IS NOT NULL",
    ),
    (
        "uq_presentaciones_descripcion",
        "presentaciones",
        "lower(trim(descripcion))",
        None,
    ),
    (
        "uq_presentaciones_codigo",
        "presentaciones",
        "lower(trim(codigo))",
        "codigo IS NOT NULL",
    ),
    # `sku` ya tenía un índice único (ix_productos_sku), pero distinguía
    # mayúsculas: "abc-1" y "ABC-1" convivían siendo el mismo producto.
    ("uq_productos_sku", "productos", "lower(trim(sku))", None),
    (
        "uq_productos_codigo_barras",
        "productos",
        "lower(trim(codigo_barras))",
        "codigo_barras IS NOT NULL",
    ),
]


def upgrade() -> None:
    for nombre, tabla, expresion, condicion in INDICES:
        where = f" WHERE {condicion}" if condicion else ""
        op.execute(
            f'CREATE UNIQUE INDEX IF NOT EXISTS "{nombre}" '
            f"ON public.{tabla} ({expresion}){where}"
        )
    # El índice de búsqueda por sku también se fue con la limpieza.
    op.execute("CREATE INDEX IF NOT EXISTS ix_productos_sku ON public.productos (sku)")


def downgrade() -> None:
    for nombre, _, _, _ in INDICES:
        op.execute(f'DROP INDEX IF EXISTS public."{nombre}"')
