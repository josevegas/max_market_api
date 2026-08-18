"""Fechas del negocio.

El servidor puede correr en UTC (lo habitual en cloud) mientras la operación
es peruana. `date.today()` devuelve el día del servidor, así que entre las
19:00 y la medianoche de Lima ya sería "mañana" en UTC: un precio con
`fecha_inicio` de mañana entraría en vigor cinco horas antes de tiempo.

Por eso las fechas de negocio se calculan siempre contra America/Lima y no
contra el reloj de la máquina.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

ZONA_PERU = ZoneInfo("America/Lima")


def ahora_en_peru() -> datetime:
    """Instante actual, con huso horario."""
    return datetime.now(ZONA_PERU)


def hoy_en_peru() -> date:
    """El día que es en Perú, independientemente de dónde esté el servidor."""
    return ahora_en_peru().date()
