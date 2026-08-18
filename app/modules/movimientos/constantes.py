"""Estados con significado de negocio dentro de la cadena de compras.

`estados` es un catálogo abierto: cualquiera puede dar de alta "En revisión" o
"Anulado" y la aplicación no tiene por qué enterarse. Pero cuatro de esos
estados **sí** deciden si la cadena avanza, y el código necesita reconocerlos.

Se reconocen por `codigo` y no por `descripcion` a propósito: la descripción es
texto que se edita desde la API ("Aprobado", "APROBADO", "Aprobada") y con eso
la regla dejaría de aplicar sin que nadie tocase una línea de código. El código
es corto, estable y la migración que siembra estas cuatro filas lo fija.
"""

from __future__ import annotations

#: Recién creado. No habilita el siguiente documento de la cadena.
CODIGO_PENDIENTE = "PEN"
#: Visado. Es el único estado desde el que la cadena avanza.
CODIGO_APROBADO = "APR"
#: La mercadería de la guía entró al almacén.
CODIGO_RECEPCIONADO = "REC"
#: El documento ya cumplió su función: lo que pedía llegó.
CODIGO_ATENDIDO = "ATE"

#: Las filas que siembra la migración. Se listan acá para que el seed y las
#: constantes no puedan decir cosas distintas.
ESTADOS_CANONICOS: tuple[tuple[str, str], ...] = (
    ("Pendiente", CODIGO_PENDIENTE),
    ("Aprobado", CODIGO_APROBADO),
    ("Recepcionado", CODIGO_RECEPCIONADO),
    ("Atendido", CODIGO_ATENDIDO),
)
