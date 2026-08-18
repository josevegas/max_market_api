"""producto: marca del fabricante y unidades de compra y venta

Revision ID: c1d47e93a2f5
Revises: f9a2c7d41b08
Create Date: 2026-08-17 19:55:02.771904

`unidad_compra` y `unidad_venta` son NOT NULL, así que en una tabla con
productos cargados no se pueden agregar sin más. La migración las crea
nullables, rellena las filas existentes con la unidad mínima (factor 1) y solo
entonces las marca NOT NULL. Si hay productos y no hay ninguna unidad que sirva
de relleno, corta con un mensaje que dice qué falta, en vez de dejar la
migración a medias con un error de integridad de PostgreSQL.

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c1d47e93a2f5"
down_revision: Union[str, None] = "f9a2c7d41b08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "productos", sa.Column("marca_fabricante", sa.String(length=25), nullable=True)
    )
    op.add_column("productos", sa.Column("unidad_compra", sa.UUID(), nullable=True))
    op.add_column("productos", sa.Column("unidad_venta", sa.UUID(), nullable=True))

    conexion = op.get_bind()
    hay_productos = conexion.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM productos)")
    ).scalar()

    if hay_productos:
        # La unidad mínima es la de factor 1: es la que no cambia el número al
        # convertir, así que rellenar con ella no altera ninguna cuenta.
        relleno = conexion.execute(
            sa.text(
                """
                SELECT u.id
                FROM unidades_medida u
                JOIN tabla_equivalencia e ON e.unidad_medida_id = u.id
                WHERE e.factor_conversion = 1
                  AND u.is_active AND e.is_active
                ORDER BY u.created_at
                LIMIT 1
                """
            )
        ).scalar()
        if relleno is None:
            raise RuntimeError(
                "Hay productos cargados y ninguna unidad de medida con factor "
                "de conversión 1 con la que rellenar `unidad_compra` y "
                "`unidad_venta`. Registre la unidad mínima y vuelva a migrar."
            )
        conexion.execute(
            sa.text(
                "UPDATE productos SET unidad_compra = :u, unidad_venta = :u "
                "WHERE unidad_compra IS NULL OR unidad_venta IS NULL"
            ),
            {"u": relleno},
        )

    op.alter_column("productos", "unidad_compra", nullable=False)
    op.alter_column("productos", "unidad_venta", nullable=False)

    op.create_index(
        op.f("ix_productos_unidad_compra"), "productos", ["unidad_compra"], unique=False
    )
    op.create_index(
        op.f("ix_productos_unidad_venta"), "productos", ["unidad_venta"], unique=False
    )
    # RESTRICT y no CASCADE: borrar una unidad de medida no puede llevarse por
    # delante los productos que la usan.
    op.create_foreign_key(
        op.f("fk_productos_unidad_compra_unidades_medida"),
        "productos",
        "unidades_medida",
        ["unidad_compra"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_productos_unidad_venta_unidades_medida"),
        "productos",
        "unidades_medida",
        ["unidad_venta"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_productos_unidad_venta_unidades_medida"),
        "productos",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_productos_unidad_compra_unidades_medida"),
        "productos",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_productos_unidad_venta"), table_name="productos")
    op.drop_index(op.f("ix_productos_unidad_compra"), table_name="productos")
    op.drop_column("productos", "unidad_venta")
    op.drop_column("productos", "unidad_compra")
    op.drop_column("productos", "marca_fabricante")
