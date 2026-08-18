"""recepcion, recepcion_detalle y los estados canonicos de la cadena

Revision ID: f9a2c7d41b08
Revises: 295e2b236ed7
Create Date: 2026-08-13 10:12:41.203118

Las cuatro filas de `estados` se siembran acá y no en un script aparte: la
cadena de compras las necesita para operar (un pedido solo nace de un
requerimiento con codigo 'APR'), así que una base migrada pero sin sembrar
sería una base en la que no se puede comprar nada.

El INSERT es idempotente: si alguien ya dio de alta esos codigos por la API, se
respetan sus filas en vez de duplicarlas.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f9a2c7d41b08"
down_revision: Union[str, None] = "295e2b236ed7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ESTADOS = (
    ("Pendiente", "PEN"),
    ("Aprobado", "APR"),
    ("Recepcionado", "REC"),
    ("Atendido", "ATE"),
)


def upgrade() -> None:
    op.create_table(
        "recepcion",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("guia_remision_id", sa.UUID(), nullable=True),
        # Sin FK: la tabla `facturas` todavía no existe (ver el modelo).
        sa.Column("factura_id", sa.UUID(), nullable=True),
        sa.Column("orden_compra_id", sa.UUID(), nullable=True),
        sa.Column("almacen_id", sa.UUID(), nullable=False),
        sa.Column("estado_id", sa.UUID(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("observaciones", sa.String(length=500), nullable=True),
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
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["almacen_id"],
            ["almacenes.id"],
            name=op.f("fk_recepcion_almacen_id_almacenes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["estado_id"],
            ["estados.id"],
            name=op.f("fk_recepcion_estado_id_estados"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["guia_remision_id"],
            ["guia_remision.id"],
            name=op.f("fk_recepcion_guia_remision_id_guia_remision"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["orden_compra_id"],
            ["orden_compra.id"],
            name=op.f("fk_recepcion_orden_compra_id_orden_compra"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recepcion")),
    )
    op.create_index(
        op.f("ix_recepcion_almacen_id"), "recepcion", ["almacen_id"], unique=False
    )
    op.create_index(
        op.f("ix_recepcion_estado_id"), "recepcion", ["estado_id"], unique=False
    )
    op.create_index(
        op.f("ix_recepcion_factura_id"), "recepcion", ["factura_id"], unique=False
    )
    op.create_index(
        op.f("ix_recepcion_guia_remision_id"),
        "recepcion",
        ["guia_remision_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recepcion_orden_compra_id"),
        "recepcion",
        ["orden_compra_id"],
        unique=False,
    )

    op.create_table(
        "recepcion_detalle",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("recepcion_id", sa.UUID(), nullable=False),
        sa.Column("producto_id", sa.UUID(), nullable=False),
        sa.Column("unidad_medida_id", sa.UUID(), nullable=False),
        sa.Column(
            "cantidad_esperada", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "cantidad_ingresada", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "cantidad_devuelta", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "precio_unitario",
            sa.Numeric(precision=12, scale=2),
            server_default="0",
            nullable=False,
        ),
        sa.Column("codigo_lote", sa.String(length=30), nullable=True),
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
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.CheckConstraint(
            "cantidad_esperada >= 0 AND cantidad_ingresada >= 0 "
            "AND cantidad_devuelta >= 0",
            name=op.f("ck_recepcion_detalle_cantidades_no_negativas"),
        ),
        sa.ForeignKeyConstraint(
            ["producto_id"],
            ["productos.id"],
            name=op.f("fk_recepcion_detalle_producto_id_productos"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recepcion_id"],
            ["recepcion.id"],
            name=op.f("fk_recepcion_detalle_recepcion_id_recepcion"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["unidad_medida_id"],
            ["unidades_medida.id"],
            name=op.f("fk_recepcion_detalle_unidad_medida_id_unidades_medida"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recepcion_detalle")),
        sa.UniqueConstraint(
            "recepcion_id", "producto_id", name="uq_recepcion_detalle_producto"
        ),
    )
    op.create_index(
        op.f("ix_recepcion_detalle_producto_id"),
        "recepcion_detalle",
        ["producto_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recepcion_detalle_recepcion_id"),
        "recepcion_detalle",
        ["recepcion_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recepcion_detalle_unidad_medida_id"),
        "recepcion_detalle",
        ["unidad_medida_id"],
        unique=False,
    )

    for descripcion, codigo in ESTADOS:
        op.execute(
            sa.text(
                "INSERT INTO estados (descripcion, codigo) "
                "SELECT :descripcion, :codigo "
                "WHERE NOT EXISTS (SELECT 1 FROM estados WHERE codigo = :codigo)"
            ).bindparams(descripcion=descripcion, codigo=codigo)
        )


def downgrade() -> None:
    codigos = tuple(codigo for _, codigo in ESTADOS)
    op.execute(
        sa.text("DELETE FROM estados WHERE codigo IN :codigos").bindparams(
            sa.bindparam("codigos", value=codigos, expanding=True)
        )
    )

    op.drop_index(
        op.f("ix_recepcion_detalle_unidad_medida_id"), table_name="recepcion_detalle"
    )
    op.drop_index(
        op.f("ix_recepcion_detalle_recepcion_id"), table_name="recepcion_detalle"
    )
    op.drop_index(
        op.f("ix_recepcion_detalle_producto_id"), table_name="recepcion_detalle"
    )
    op.drop_table("recepcion_detalle")

    op.drop_index(op.f("ix_recepcion_orden_compra_id"), table_name="recepcion")
    op.drop_index(op.f("ix_recepcion_guia_remision_id"), table_name="recepcion")
    op.drop_index(op.f("ix_recepcion_factura_id"), table_name="recepcion")
    op.drop_index(op.f("ix_recepcion_estado_id"), table_name="recepcion")
    op.drop_index(op.f("ix_recepcion_almacen_id"), table_name="recepcion")
    op.drop_table("recepcion")
