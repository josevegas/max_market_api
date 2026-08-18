"""Tareas que se ejecutan fuera del ciclo de una petición.

Se lanzan desde el programador de tareas del sistema (o cron), no desde un
scheduler embebido: con varios workers de uvicorn un scheduler en proceso
correría la misma tarea una vez por worker.
"""
