"""tabla facturas, y la FK que recepcion.factura_id esperaba

El módulo existía como modelo y schema pero sin tabla, sin registrar en
`app/db/models.py` y sin endpoints: no había forma de dar de alta una factura.

`recepcion.factura_id` se había dejado sin `ForeignKey` a propósito, porque no
se puede apuntar a una tabla que no existe (ver el comentario en `Recepcion`).
Ahora que existe, se ata.

Revision ID: c8b3f5a02d17
Revises: b4d1e8f37c25
Create Date: 2026-08-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c8b3f5a02d17"
down_revision = "b4d1e8f37c25"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "facturas",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("proveedor_id", sa.UUID(), nullable=False),
        sa.Column("serie", sa.String(length=4), nullable=False),
        sa.Column("correlativo", sa.String(length=8), nullable=False),
        sa.Column("guia_remision_id", sa.UUID(), nullable=True),
        sa.Column("orden_compra_id", sa.UUID(), nullable=False),
        sa.Column("monto_total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("monto_pago", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("fecha_emision", sa.Date(), nullable=False),
        sa.Column("fecha_vencimiento", sa.Date(), nullable=False),
        sa.Column("estado_id", sa.UUID(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "fecha_vencimiento >= fecha_emision",
            name=op.f("ck_facturas_chk_factura_vencimiento_posterior"),
        ),
        sa.CheckConstraint(
            "monto_pago <= monto_total",
            name=op.f("ck_facturas_chk_factura_pago_no_supera_total"),
        ),
        sa.ForeignKeyConstraint(
            ["proveedor_id"],
            ["empresas.id"],
            name=op.f("fk_facturas_proveedor_id_empresas"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["guia_remision_id"],
            ["guia_remision.id"],
            name=op.f("fk_facturas_guia_remision_id_guia_remision"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["orden_compra_id"],
            ["orden_compra.id"],
            name=op.f("fk_facturas_orden_compra_id_orden_compra"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["estado_id"],
            ["estados.id"],
            name=op.f("fk_facturas_estado_id_estados"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_facturas")),
        sa.UniqueConstraint(
            "proveedor_id",
            "serie",
            "correlativo",
            name=op.f("uq_factura_numero"),
        ),
    )
    op.create_index(
        op.f("ix_facturas_proveedor_id"), "facturas", ["proveedor_id"], unique=False
    )
    op.create_index(
        op.f("ix_facturas_guia_remision_id"),
        "facturas",
        ["guia_remision_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_facturas_orden_compra_id"),
        "facturas",
        ["orden_compra_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_facturas_estado_id"), "facturas", ["estado_id"], unique=False
    )

    # La columna ya existía apuntando al vacío. Las filas que tuvieran algo
    # cargado no pueden respaldarse contra una tabla recién creada, así que se
    # limpian antes de atar la FK: dejarlas rompería el ALTER.
    op.execute("UPDATE recepcion SET factura_id = NULL WHERE factura_id IS NOT NULL")
    op.create_foreign_key(
        op.f("fk_recepcion_factura_id_facturas"),
        "recepcion",
        "facturas",
        ["factura_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_recepcion_factura_id_facturas"), "recepcion", type_="foreignkey"
    )
    op.drop_index(op.f("ix_facturas_estado_id"), table_name="facturas")
    op.drop_index(op.f("ix_facturas_orden_compra_id"), table_name="facturas")
    op.drop_index(op.f("ix_facturas_guia_remision_id"), table_name="facturas")
    op.drop_index(op.f("ix_facturas_proveedor_id"), table_name="facturas")
    op.drop_table("facturas")
