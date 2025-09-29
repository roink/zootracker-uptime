# Logging package overview

This directory contains the backend logging utilities split into focused modules:

- `config.py` configures the application logging tree and exposes the `configure_logging` entrypoint.
- `context.py` defines context variables and helpers to bind request identifiers and user metadata.
- `filters.py` houses logging filters for request context injection and privacy safeguards.
- `formatter.py` implements the ECS-compatible JSON formatter.
- `handlers.py` provides file-based handler helpers.
- `ip_utils.py` contains IP anonymisation helpers shared by filters and privacy logic.
- `privacy.py` implements the structured sanitisation helpers.

Keep new modules narrowly scoped; prefer adding well-documented functions over large classes. Maintain parity with the re-exported API in `__init__.py` when adding new functionality.
