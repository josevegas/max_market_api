# max_market_api

API de consumo para software de Max Market.

FastAPI + SQLAlchemy 2 (async) + PostgreSQL, con Alembic para las migraciones.
Base de datos de **esquema único**: todas las tablas viven en `public`.

## Puesta en marcha

```bash
python -m venv .venv && .venv\Scripts\activate     # Windows
pip install -r requirements.txt
copy .env.example .env                             # y completar los valores
alembic upgrade head
uvicorn app.main:app --reload
```

- Documentación interactiva: http://localhost:8000/docs
- Chequeo de vida: http://localhost:8000/salud

## Estructura

```
app/
  core/
    config.py        Settings leídas del .env (pydantic-settings)
    dependencies.py  get_db: sesión por request
  db/
    base.py          Base declarativa + convención de nombres de constraints
    mixins.py        AuditMixin (created_at/by, updated_at/by, is_active)
    models.py        Registro central de modelos para Alembic
    session.py       Engine async y fábrica de sesiones
  api/v1/router.py   Router raíz donde se cuelga cada módulo
  modules/<dominio>/ api / models / schemas / services
  main.py            Aplicación FastAPI
alembic/             env.py async, apuntado a Base.metadata
```

## Migraciones

```bash
alembic revision --autogenerate -m "descripción"
alembic upgrade head
alembic downgrade -1
```

Dos cosas que hay que respetar para que `--autogenerate` funcione:

1. **Todo modelo nuevo se importa en `app/db/models.py`.** Alembic solo ve lo
   que esté en `Base.metadata`; un modelo sin importar se ignora en silencio y
   sus tablas quedan fuera.
2. **La URL de la base sale del `.env`**, no de `alembic.ini` — ese archivo se
   versiona y no debe llevar credenciales.

## Variables de entorno

| Variable         | Para qué                                              |
|------------------|-------------------------------------------------------|
| `DATABASE_URL`   | PostgreSQL con driver async (`postgresql+asyncpg://`) |
| `URL_API`        | API externa de consultas (api.json.pe)                |
| `API_JSON_TOKEN` | Token de esa API                                      |

`.env` está en `.gitignore`; el que se versiona es `.env.example`.
