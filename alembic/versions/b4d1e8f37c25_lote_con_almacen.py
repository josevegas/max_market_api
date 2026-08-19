"""producto_lote con almacén, y la guía pasa a ser opcional

El lote no decía dónde estaba la mercadería, así que el stock no se podía
comparar contra el `stock_minimo` de `producto_almacen`, que sí es por almacén.
La guía pasa a opcional porque una recepción contra orden de compra directa no
tiene guía y su stock también cuenta.

Revision ID: b4d1e8f37c25
Revises: b4e81d5c7a92
Create Date: 2026-08-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b4d1e8f37c25"
down_revision = "b4e81d5c7a92"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Entra nullable para poder rellenarla: un `NOT NULL` de entrada no deja
    # migrar una tabla que ya tenga lotes.
    op.add_column("producto_lote", sa.Column("almacen_id", sa.UUID(), nullable=True))
    # El almacén de los lotes que ya existen sale de la recepción de su guía,
    # que es la única que sabe a dónde entró la mercadería.
    op.execute(
        """
        UPDATE producto_lote AS pl
           SET almacen_id = r.almacen_id
          FROM recepcion AS r
         WHERE r.guia_remision_id = pl.guia_remision_id
           AND r.is_active
        """
    )
    # Si algún lote se queda sin almacén, el `NOT NULL` corta la migración. Es
    # lo correcto: significa que hay stock del que nadie sabe dónde está, y
    # elegirle un almacén acá sería inventar el dato.
    op.alter_column("producto_lote", "almacen_id", nullable=False)
    op.create_foreign_key(
        op.f("fk_producto_lote_almacen_id_almacenes"),
        "producto_lote",
        "almacenes",
        ["almacen_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_producto_lote_almacen_id"),
        "producto_lote",
        ["almacen_id"],
        unique=False,
    )

    op.alter_column("producto_lote", "guia_remision_id", nullable=True)

    # El código de lote se repite entre almacenes: son dos pilas físicas.
    op.drop_constraint(op.f("uq_producto_lote_codigo"), "producto_lote", type_="unique")
    op.create_unique_constraint(
        op.f("uq_producto_lote_codigo"),
        "producto_lote",
        ["almacen_id", "producto_id", "codigo_lote"],
    )


def downgrade() -> None:
    op.drop_constraint(op.f("uq_producto_lote_codigo"), "producto_lote", type_="unique")
    op.create_unique_constraint(
        op.f("uq_producto_lote_codigo"),
        "producto_lote",
        ["producto_id", "codigo_lote"],
    )
    # Los lotes sin guía se quedaron sin a qué volver: se dan de baja en vez de
    # borrarlos, que es como este esquema retira las filas.
    op.execute(
        "UPDATE producto_lote SET is_active = false WHERE guia_remision_id IS NULL"
    )
    op.alter_column("producto_lote", "guia_remision_id", nullable=False)

    op.drop_index(op.f("ix_producto_lote_almacen_id"), table_name="producto_lote")
    op.drop_constraint(
        op.f("fk_producto_lote_almacen_id_almacenes"),
        "producto_lote",
        type_="foreignkey",
    )
    op.drop_column("producto_lote", "almacen_id")
