"""creando tabla sub_familia

Revision ID: f5200d51f618
Revises: 8b68fd770cd9
Create Date: 2026-08-05 16:39:12.394689

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5200d51f618"
down_revision: str | None = "8b68fd770cd9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sub_familias",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("codigo", sa.String(length=3), nullable=True),
        sa.Column(
            "familia_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("familias.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Campos heredados de AuditMixin (ajusta las columnas si tu mixin difiere)
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
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
            nullable=True,
        ),
        schema="public",
    )


def downgrade() -> None:
    op.drop_table("sub_familias", schema="public")
