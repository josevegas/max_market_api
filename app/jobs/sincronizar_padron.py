"""Sincroniza los padrones de agentes de SUNAT y reconcilia las empresas.

Pensado para el programador de tareas, semanal o quincenal:

    python -m app.jobs.sincronizar_padron

Sale con código 1 si algo falla, para que el programador lo marque como error
en vez de darlo por bueno. El detalle del fallo queda además en
`padron_sincronizaciones`.
"""

from __future__ import annotations

import asyncio
import sys

from app.db.session import AsyncSessionLocal
from app.modules.proveedores.services.padron_agentes import (
    PadronAgentesService,
    PadronError,
)


async def _principal() -> int:
    async with AsyncSessionLocal() as db:
        try:
            resumen = await PadronAgentesService(db).sincronizar()
        except PadronError as e:
            print(f"[padron] FALLO: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(
                f"[padron] FALLO inesperado: {type(e).__name__}: {e}", file=sys.stderr
            )
            return 1

    print(
        f"[padron] OK - retencion={resumen.filas_retencion} "
        f"percepcion={resumen.filas_percepcion} "
        f"empresas_actualizadas={resumen.empresas_actualizadas}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_principal()))
