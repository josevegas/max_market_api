"""almacenes y unidades de medida

`producto_lote` queda fuera a propósito: su FK apunta a `guia_remision`, que
arrastra toda la cadena de `movimientos` (orden_compra → cotizaciones →
pedidos → requerimientos → estados). Se creará cuando ese módulo esté
definido.

Revision ID: c3e7a94d15b8
Revises: b2d5f1a83c47
Create Date: 2026-08-11

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3e7a94d15b8"
down_revision: str | None = "b2d5f1a83c47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: (índice, tabla, expresión, condición parcial)
INDICES = [
    (
        "uq_unidades_medida_descripcion",
        "unidades_medida",
        "lower(trim(descripcion))",
        None,
    ),
    ("uq_unidades_medida_codigo", "unidades_medida", "lower(trim(codigo))", None),
    ("uq_almacenes_market_nombre", "almacenes", "market_id, lower(trim(nombre))", None),
    ("uq_almacenes_codigo", "almacenes", "lower(trim(codigo))", None),
]


def _auditoria() -> list[sa.Column]:
    return [
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
        sa.Column("created_by", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", sa.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
    ]


def _id() -> sa.Column:
    return sa.Column(
        "id",
        sa.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "unidades_medida",
        _id(),
        sa.Column("descripcion", sa.String(length=50), nullable=False),
        sa.Column("codigo", sa.String(length=10), nullable=False),
        *_auditoria(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_unidades_medida")),
    )

    op.create_table(
        "tabla_equivalencia",
        _id(),
        sa.Column("unidad_medida_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "factor_conversion", sa.Integer(), nullable=False, server_default="1"
        ),
        *_auditoria(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tabla_equivalencia")),
        sa.ForeignKeyConstraint(
            ["unidad_medida_id"],
            ["unidades_medida.id"],
            name=op.f("fk_tabla_equivalencia_unidad_medida_id_unidades_medida"),
        ),
    )
    op.create_index(
        op.f("ix_tabla_equivalencia_unidad_medida_id"),
        "tabla_equivalencia",
        ["unidad_medida_id"],
    )

    op.create_table(
        "almacenes",
        _id(),
        sa.Column("market_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("nombre", sa.String(length=50), nullable=False),
        sa.Column("codigo", sa.String(length=10), nullable=False),
        *_auditoria(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_almacenes")),
        sa.ForeignKeyConstraint(
            ["market_id"],
            ["markets.id"],
            name=op.f("fk_almacenes_market_id_markets"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(op.f("ix_almacenes_market_id"), "almacenes", ["market_id"])

    op.create_table(
        "producto_almacen",
        _id(),
        sa.Column("almacen_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("producto_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("unidad_medida_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("stock_minimo", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("stock_maximo", sa.Integer(), nullable=True),
        sa.Column("precio_venta_tienda", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "estado", sa.String(length=50), nullable=False, server_default="disponible"
        ),
        *_auditoria(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_producto_almacen")),
        sa.ForeignKeyConstraint(
            ["almacen_id"],
            ["almacenes.id"],
            name=op.f("fk_producto_almacen_almacen_id_almacenes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["producto_id"],
            ["productos.id"],
            name=op.f("fk_producto_almacen_producto_id_productos"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["unidad_medida_id"],
            ["unidades_medida.id"],
            name=op.f("fk_producto_almacen_unidad_medida_id_unidades_medida"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "estado IN ('disponible','agotado','inmovilizado')",
            name="chk_producto_almacen_estado",
        ),
        sa.UniqueConstraint("almacen_id", "producto_id", name="uq_producto_almacen"),
    )
    op.create_index(
        op.f("ix_producto_almacen_almacen_id"), "producto_almacen", ["almacen_id"]
    )
    op.create_index(
        op.f("ix_producto_almacen_producto_id"), "producto_almacen", ["producto_id"]
    )
    op.create_index(
        op.f("ix_producto_almacen_unidad_medida_id"),
        "producto_almacen",
        ["unidad_medida_id"],
    )

    for nombre, tabla, expresion, condicion in INDICES:
        where = f" WHERE {condicion}" if condicion else ""
        op.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {nombre} ON {tabla} ({expresion}){where}"
        )


def downgrade() -> None:
    for nombre, *_ in INDICES:
        op.execute(f"DROP INDEX IF EXISTS {nombre}")
    op.drop_table("producto_almacen")
    op.drop_table("almacenes")
    op.drop_table("tabla_equivalencia")
    op.drop_table("unidades_medida")
