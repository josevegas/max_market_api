"""precio de compra por lote, y el precio de tienda que sale de ahí

`precio_venta_tienda` se cargaba a mano y nada lo ataba a lo que la mercadería
costó. Ahora cada lote guarda lo que costó una unidad de venta suya, y el precio
de la tienda sale del lote más caro que quede con existencias: vender por debajo
de eso sería perder plata sobre la partida que todavía está en el almacén.

`precio_manual` deja fijar el precio a mano —una promoción— sin que la
sincronización lo pise.

Los lotes que ya existan quedan con `precio_compra` en cero hasta que su
recepción vuelva a sincronizarse: el costo hay que convertirlo a la unidad de
venta, y eso no se puede resolver en SQL sin la tabla de equivalencias de por
medio. Cero es honesto —"no se sabe"— y no ensucia el máximo hacia arriba.

Revision ID: d2a71c4e9f30
Revises: c8b3f5a02d17
Create Date: 2026-08-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d2a71c4e9f30"
down_revision = "c8b3f5a02d17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "producto_lote",
        sa.Column(
            "precio_compra",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "producto_almacen",
        sa.Column(
            "precio_manual",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    # Las fichas que ya existen se cargaron a mano: marcarlas como manuales
    # evita que la primera sincronización les cambie el precio sin que nadie
    # lo haya pedido. Quien quiera pasarlas a automático manda `precio_manual`
    # en false.
    op.execute("UPDATE producto_almacen SET precio_manual = true")


def downgrade() -> None:
    op.drop_column("producto_almacen", "precio_manual")
    op.drop_column("producto_lote", "precio_compra")
