"""unicidad de markets y bancos

Índices funcionales sobre `lower(trim(...))`, como los del catálogo de
productos: quien carga los datos entiende que "Norte" y "norte " son el mismo
código, y sin esto dos peticiones simultáneas pasarían las dos la validación
del servicio y crearían el duplicado igual.

Los códigos opcionales llevan índice parcial (`WHERE ... IS NOT NULL`): varios
registros sin código no compiten entre sí.

Revision ID: b2d5f1a83c47
Revises: a1c4e9f2b730
Create Date: 2026-08-10

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2d5f1a83c47"
down_revision: str | None = "a1c4e9f2b730"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: (índice, tabla, expresión, condición parcial)
INDICES = [
    ("uq_zonas_nombre", "zonas", "lower(trim(nombre))", None),
    ("uq_zonas_codigo", "zonas", "lower(trim(codigo))", None),
    ("uq_sedes_zona_nombre", "sedes", "zona_id, lower(trim(nombre))", None),
    ("uq_sedes_codigo", "sedes", "lower(trim(codigo))", None),
    ("uq_markets_sede_nombre", "markets", "sede_id, lower(trim(nombre))", None),
    ("uq_markets_codigo", "markets", "lower(trim(codigo))", None),
    ("uq_bancos_ruc", "bancos", "lower(trim(ruc))", None),
    ("uq_bancos_codigo", "bancos", "lower(trim(codigo))", "codigo IS NOT NULL"),
    ("uq_tipo_cuenta_descripcion", "tipo_cuenta", "lower(trim(descripcion))", None),
    ("uq_tipo_cuenta_codigo", "tipo_cuenta", "lower(trim(codigo))", None),
    (
        "uq_cuentas_banco_numero",
        "cuentas",
        "banco_id, lower(trim(numero_cuenta))",
        None,
    ),
]


def upgrade() -> None:
    for nombre, tabla, expresion, condicion in INDICES:
        where = f" WHERE {condicion}" if condicion else ""
        op.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {nombre} ON {tabla} ({expresion}){where}"
        )


def downgrade() -> None:
    for nombre, *_ in INDICES:
        op.execute(f"DROP INDEX IF EXISTS {nombre}")
