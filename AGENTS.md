# Agent Instructions

This repository provides a FastAPI backend for tracking zoo visits and animal sightings and a small React frontend. The backend uses a PostgreSQL database. The frontend is located under `frontend/` and is built with Vite and React. Use Bootstrap classes for styling and keep components well commented with `//` style descriptions. Prefer small components and place reusable styles in CSS files under `src/styles` instead of inline styles.

Project structure overview:

- `app/` – FastAPI application code
- `frontend/` – React/Vite web client
  - `src/components/` – shared React components
  - `src/pages/` – route pages
  - `src/styles/` – custom CSS loaded by `main.jsx`
- `tests/` – pytest suite for the backend
- `docs/` – architecture and planning documents
- `schema.sql` – database schema

## Running tests

Run the backend test suite with SQLite so it works without a PostgreSQL server:

```bash
pytest -q
```

Tests that require PostgreSQL are marked with `@pytest.mark.postgres` and are
skipped unless the `--pg` option is provided. To run them locally start the
database and execute:

```bash
docker compose up -d db
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres pytest --pg
```

Always run the tests after making changes.

## Environment setup

Activate the provided virtual environment before running tests, linting, or the app. All required Python packages are already installed there.

```bash
source venv/bin/activate
```

If you need to recreate the environment, run:

```bash
./setup_env.sh
```
This uses `requirements.txt` which must list all Python packages like `fastapi` needed to execute the backend and test suite.

### Linting

- Python: `ruff check .`
- Frontend: `npm --prefix frontend ci && npm --prefix frontend run lint`


## Translations

All user-facing strings in the frontend live in `frontend/src/locales/<lang>/common.json`. When adding new UI text:

- Add keys to both the English and German files with descriptive names (e.g. `actions.logSighting`).
- Use `useTranslation` and `t()` in components instead of hardcoded strings.
- Update documentation if necessary and run the tests and linters.

See `docs/i18n.md` for more details on the translation workflow.

## Frontend overlays

A generic modal layout is provided in `frontend/src/styles/app.css` using the
`.modal-overlay` and `.modal-box` classes. Components can use these classes to
present forms as centered overlays. Keep the modal contents narrow (max-width
around 500px) so they do not fill the entire screen on large monitors. When
opening the sighting modal from another page, pass both the ID **and** name of
the current animal and zoo in the router state. This lets the form show those
values immediately while it fetches the full lists for searching.

The dashboard now shows an **Edit** button next to each sighting. Clicking it
opens a modal overlay with the sighting pre-filled so users can update the zoo,
animal or date. The form offers **Cancel**, **Apply changes** and **Delete**
actions and is implemented using the existing `LogSighting` component. The
overlay page is mounted at `/sightings/:id/edit`.

