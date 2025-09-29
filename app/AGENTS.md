# App package overview

The `app` package hosts the FastAPI backend and supporting utilities.
Key modules and subpackages include:

- `main.py` – constructs the FastAPI application, wires middleware, and bootstraps logging.
- `config.py` – validates environment-driven settings such as tokens and CORS origins.
- `database.py` / `db_extensions.py` – provide SQLAlchemy session helpers and engine extensions.
- `models.py` & `schemas.py` – define the ORM models and Pydantic response schemas.
- `api/` – houses route handlers grouped by domain (animals, visits, users, etc.).
- `auth.py`, `rate_limit.py`, and `middleware/` – authentication, throttling, and HTTP middleware helpers.
- `logging/` – logging configuration helpers (see package-specific guide).
- `utils/` & `importers/` – shared helper functions and data import scripts.
- `metrics.py`, `triggers.py`, and `create_tables.py` – background metrics, database triggers, and setup scripts.

Keep modules focused on a single concern and prefer importing cross-cutting helpers via the relevant subpackage.
