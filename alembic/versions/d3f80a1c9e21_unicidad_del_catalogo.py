"""unicidad del catálogo

Impide registros repetidos en el maestro de productos.

Son índices **funcionales** sobre `lower(trim(...))` porque "Abarrotes" y
"abarrotes " son el mismo dato para quien carga el catálogo, y un UNIQUE normal
los dejaría pasar. Y son **parciales** (`WHERE ... IS NOT NULL`) en las columnas
opcionales: varios registros sin código no compiten entre sí.

El nombre es único dentro de su padre (dos familias distintas pueden tener una
sub familia "Granos"); los códigos y el SKU son únicos en toda la tabla.

Revision ID: d3f80a1c9e21
Revises: 4f67736b1867
Create Date: 2026-08-06 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "d3f80a1c9e21"
down_revision: Union[str, None] = "4f67736b1867"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

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
    ("uq_sub_familias_codigo", "sub_familias", "lower(trim(codigo))", "codigo IS NOT NULL"),
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
    ("uq_presentaciones_descripcion", "presentaciones", "lower(trim(descripcion))", None),
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
            f'CREATE UNIQUE INDEX "{nombre}" ON public.{tabla} ({expresion}){where}'
        )

    # El índice único anterior sobre sku queda de más: `uq_productos_sku` es
    # más estricto y lo cubre.
    op.execute("DROP INDEX IF EXISTS public.ix_productos_sku")
    op.execute("CREATE INDEX ix_productos_sku ON public.productos (sku)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.ix_productos_sku")
    op.execute("CREATE UNIQUE INDEX ix_productos_sku ON public.productos (sku)")
    for nombre, _, _, _ in INDICES:
        op.execute(f'DROP INDEX IF EXISTS public."{nombre}"')
