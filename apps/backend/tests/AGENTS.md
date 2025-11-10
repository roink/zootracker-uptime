# Tests package overview

The `tests` package contains pytest suites covering API endpoints, utilities, and database integration logic.

- `conftest.py` – shared fixtures for database sessions, clients, and sample data.
- `test_*.py` modules – organised by feature (auth, animals, imports, logging, etc.) and rely on factories from fixtures.

Keep new tests deterministic, prefer factory fixtures over inline object construction, and mark database-intensive suites with `@pytest.mark.postgres` when they require PostgreSQL.
