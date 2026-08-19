"""producto_lote sin unidad propia y con dias_alerta_vencimiento

El lote ya no lleva unidad: su cantidad va siempre en la unidad de venta del
producto, que es en la que el market mueve el stock. La unidad de la línea de
la guía (la de compra) sigue estando donde estaba; la conversión entre las dos
sale de `tabla_equivalencia`.

Revision ID: a7f2c9e41b30
Revises: c1d47e93a2f5
Create Date: 2026-08-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a7f2c9e41b30"
down_revision = "c1d47e93a2f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "producto_lote",
        sa.Column("dias_alerta_vencimiento", sa.Integer(), nullable=True),
    )
    op.drop_index(op.f("ix_producto_lote_unidad_medida_id"), table_name="producto_lote")
    op.drop_constraint(
        op.f("fk_producto_lote_unidad_medida_id_unidades_medida"),
        "producto_lote",
        type_="foreignkey",
    )
    op.drop_column("producto_lote", "unidad_medida_id")


def downgrade() -> None:
    # Vuelve como nullable: las filas existentes ya no tienen de dónde sacar la
    # unidad, y forzar un valor inventado sería peor que dejar el hueco.
    op.add_column(
        "producto_lote",
        sa.Column("unidad_medida_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_producto_lote_unidad_medida_id_unidades_medida"),
        "producto_lote",
        "unidades_medida",
        ["unidad_medida_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_producto_lote_unidad_medida_id"),
        "producto_lote",
        ["unidad_medida_id"],
        unique=False,
    )
    op.drop_column("producto_lote", "dias_alerta_vencimiento")
