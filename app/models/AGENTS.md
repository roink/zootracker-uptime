# Models package overview

The `app.models` package groups SQLAlchemy ORM types by domain to keep related
schemas together while avoiding circular imports.

- Each submodule (e.g. `geography`, `animals`, `visits`) should define models for
  a single domain and rely on string-based relationship targets when linking to
  models in other modules.
- Keep shared metadata on `app.models.Base` imported from `app.database`.
- When adding or renaming models, re-export them in `app/models/__init__.py` so
  existing imports like `from app import models` continue to work.
- Maintain deterministic ordering in `__all__` to minimise merge conflicts when
  multiple contributors touch the re-export list.
