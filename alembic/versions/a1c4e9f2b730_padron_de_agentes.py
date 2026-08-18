"""padron de agentes de retencion y percepcion

Revision ID: a1c4e9f2b730
Revises: e7a41b2c8d90
Create Date: 2026-08-10

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1c4e9f2b730"
down_revision: str | None = "e7a41b2c8d90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "padron_agentes",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("ruc", sa.String(length=11), nullable=False),
        sa.Column("tipo", sa.String(length=12), nullable=False),
        sa.Column("a_partir_de", sa.Date(), nullable=True),
        sa.Column("resolucion", sa.String(length=60), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_padron_agentes")),
        sa.UniqueConstraint("ruc", "tipo", name="uq_padron_agente"),
    )
    op.create_index(
        op.f("ix_padron_agentes_ruc"), "padron_agentes", ["ruc"], unique=False
    )

    op.create_table(
        "padron_sincronizaciones",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "ejecutada_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("filas_retencion", sa.Integer(), nullable=False),
        sa.Column("filas_percepcion", sa.Integer(), nullable=False),
        sa.Column("empresas_actualizadas", sa.Integer(), nullable=False),
        sa.Column("detalle", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_padron_sincronizaciones")),
    )


def downgrade() -> None:
    op.drop_table("padron_sincronizaciones")
    op.drop_index(op.f("ix_padron_agentes_ruc"), table_name="padron_agentes")
    op.drop_table("padron_agentes")
