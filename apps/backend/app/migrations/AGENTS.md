# Migrations package overview

The `app.migrations` package hosts Alembic metadata and revision scripts.

- `__init__.py` marks the package for discovery by Alembic.
- `versions/` contains individual revision modules with upgrade/downgrade logic.

Keep migration modules declarative, using Alembic operations helpers rather than raw SQL where possible.
