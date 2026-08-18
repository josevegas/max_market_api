"""orden compra sin proveedor y con monto total

`orden_compra.proveedor_id` duplicaba `cotizaciones.proveedor_id`: dos sitios
para el mismo dato, que podían acabar diciendo cosas distintas. Se elimina y
el proveedor se obtiene siguiendo `cotizacion_id`.

`monto_total` entra con `server_default='0'` porque la orden se crea antes que
sus líneas; a partir de ahí lo mantiene `OrdenCompraDetalleService`.

Revision ID: 4e230a25ac98
Revises: 3b346b56409a
Create Date: 2026-08-12

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4e230a25ac98"
down_revision: str | None = "3b346b56409a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orden_compra",
        sa.Column(
            "monto_total",
            sa.Numeric(precision=12, scale=2),
            server_default="0",
            nullable=False,
        ),
    )
    op.drop_index("ix_orden_compra_proveedor_id", table_name="orden_compra")
    op.drop_constraint(
        "fk_orden_compra_proveedor_id_empresas", "orden_compra", type_="foreignkey"
    )
    op.drop_column("orden_compra", "proveedor_id")


def downgrade() -> None:
    # En tres pasos y no como NOT NULL de golpe: con órdenes ya cargadas, un
    # `add_column` obligatorio sin valor falla. El dato se reconstruye desde la
    # cotización, que es de donde salía.
    op.add_column("orden_compra", sa.Column("proveedor_id", sa.UUID(), nullable=True))
    op.execute(
        """
        UPDATE orden_compra o
           SET proveedor_id = c.proveedor_id
          FROM cotizaciones c
         WHERE c.id = o.cotizacion_id
        """
    )
    op.alter_column("orden_compra", "proveedor_id", nullable=False)
    op.create_foreign_key(
        "fk_orden_compra_proveedor_id_empresas",
        "orden_compra",
        "empresas",
        ["proveedor_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_orden_compra_proveedor_id", "orden_compra", ["proveedor_id"], unique=False
    )
    op.drop_column("orden_compra", "monto_total")
