"""estados canonicos OBS (Observado) y RCH (Rechazado)

Faltaban las dos salidas negativas de la revision: hasta acá un documento solo
podía quedarse pendiente o aprobarse, y quien lo visaba no tenía cómo devolverlo.

Las bases que venían operando ya tenían filas equivalentes dadas de alta por la
API, con los codigos largos 'OBSERVADO' y 'RECHAZADO'. No se borran: hay
documentos apuntándolas y el FK de `recepcion` es ON DELETE CASCADE, así que un
DELETE se llevaría los documentos por delante. Se reapuntan a la fila canónica
y la vieja queda desactivada, que es la baja lógica del resto del sistema.

Revision ID: b4e81d5c7a92
Revises: a7f2c9e41b30
Create Date: 2026-08-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b4e81d5c7a92"
down_revision = "a7f2c9e41b30"
branch_labels = None
depends_on = None


#: Copia literal de las filas nuevas de `ESTADOS_CANONICOS`. Se repite acá y no
#: se importa del paquete a propósito: la migración describe el estado de la
#: base en este punto de la historia, y si mañana la constante cambia, esta
#: revisión tiene que seguir aplicando lo mismo que aplicó el día que corrió.
NUEVOS: tuple[tuple[str, str], ...] = (
    ("Observado", "OBS"),
    ("Rechazado", "RCH"),
)

#: `codigo` largo que quedó en las bases viejas -> `codigo` canónico que lo
#: reemplaza. La descripción no sirve para emparejarlos: es editable.
LEGACY: tuple[tuple[str, str], ...] = (
    ("OBSERVADO", "OBS"),
    ("RECHAZADO", "RCH"),
)

#: Todo lo que apunta a `estados`. Ninguna de estas columnas es nullable.
TABLAS = (
    "requerimientos",
    "pedidos",
    "cotizaciones",
    "orden_compra",
    "guia_remision",
    "recepcion",
)


def upgrade() -> None:
    # Idempotente, igual que el seed de f9a2c7d41b08: una base que ya tenga el
    # codigo (por API o por un upgrade a medias) conserva su fila.
    for descripcion, codigo in NUEVOS:
        op.execute(
            sa.text(
                "INSERT INTO estados (descripcion, codigo) "
                "SELECT :descripcion, :codigo "
                "WHERE NOT EXISTS (SELECT 1 FROM estados WHERE codigo = :codigo)"
            ).bindparams(descripcion=descripcion, codigo=codigo)
        )

    for viejo, nuevo in LEGACY:
        for tabla in TABLAS:
            op.execute(
                sa.text(
                    f"UPDATE {tabla} SET estado_id = ("
                    "  SELECT id FROM estados WHERE codigo = :nuevo LIMIT 1"
                    ") WHERE estado_id IN ("
                    "  SELECT id FROM estados WHERE codigo = :viejo"
                    ")"
                ).bindparams(nuevo=nuevo, viejo=viejo)
            )
        # Desactivar y no borrar: el DELETE cascadearía sobre `recepcion`.
        op.execute(
            sa.text(
                "UPDATE estados SET is_active = false WHERE codigo = :viejo"
            ).bindparams(viejo=viejo)
        )


def downgrade() -> None:
    """Deshace el reapuntado y quita las filas nuevas, en ese orden.

    El DELETE va último y con guarda: `recepcion.estado_id` es ON DELETE
    CASCADE, así que borrar un estado que todavía tenga documentos colgando se
    llevaría los documentos. Si en OBS/RCH quedó algo que no puede volver a la
    fila legacy —porque esta base nunca la tuvo—, la fila canónica se conserva.
    """
    for viejo, nuevo in LEGACY:
        op.execute(
            sa.text(
                "UPDATE estados SET is_active = true WHERE codigo = :viejo"
            ).bindparams(viejo=viejo)
        )
        for tabla in TABLAS:
            op.execute(
                sa.text(
                    f"UPDATE {tabla} SET estado_id = ("
                    "  SELECT id FROM estados WHERE codigo = :viejo LIMIT 1"
                    ") WHERE estado_id IN ("
                    "  SELECT id FROM estados WHERE codigo = :nuevo"
                    ") AND EXISTS (SELECT 1 FROM estados WHERE codigo = :viejo)"
                ).bindparams(nuevo=nuevo, viejo=viejo)
            )

    referencias = " OR ".join(
        f"EXISTS (SELECT 1 FROM {tabla} WHERE {tabla}.estado_id = estados.id)"
        for tabla in TABLAS
    )
    op.execute(
        sa.text(
            "DELETE FROM estados WHERE codigo IN :codigos "
            f"AND NOT ({referencias})"
        ).bindparams(
            sa.bindparam("codigos", value=tuple(c for _, c in NUEVOS), expanding=True)
        )
    )
