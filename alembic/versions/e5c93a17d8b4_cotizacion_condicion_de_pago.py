"""cotizaciones.condicion_pago_dias

Los días de crédito que ofrece el proveedor. Es uno de los cuatro criterios con
los que el comparativo de cotizaciones decide cuál conviene, y el único que no
se podía sacar de ninguna columna existente.

Entra NOT NULL con default 0 —contado— y no nullable: el puntaje tendría que
decidir si un nulo vale como contado o como "sin dato", y con 0 la cotización
que nadie completó queda en el peor caso para el proveedor. Premiar el dato
faltante habría sido lo contrario de lo que se busca.

Revision ID: e5c93a17d8b4
Revises: d2a71c4e9f30
Create Date: 2026-08-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e5c93a17d8b4"
down_revision = "d2a71c4e9f30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cotizaciones",
        sa.Column(
            "condicion_pago_dias",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("cotizaciones", "condicion_pago_dias")
