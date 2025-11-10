# Importers package overview

The `app.importers` package contains scripts for ingesting reference data into the database.
Modules cover specific datasets:

- `animals.py`, `taxonomy.py`, and `categories.py` – animal metadata, hierarchical taxonomy, and categorisation loading.
- `zoos.py` & `regions.py` – facility profiles and regional groupings.
- `links.py` – external resource links for animals and zoos.
- `images.py` – image asset ingestion and association.

Keep importers idempotent and safe to run repeatedly; prefer composable helper functions re-used by the CLI entry points in `app.import_utils`.
