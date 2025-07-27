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
- `example_data/` and `schema.sql` – demo data and database schema

## Running tests

Use the provided Docker Compose environment for tests. Start the services and execute pytest in the app container:

```bash
python -m pytest
```

Always run the tests after making changes.

## Environment setup

Create a virtual environment and install dependencies before running tests or the app:

```bash
./setup_env.sh
```

This uses `requirements.txt` which must list all Python packages like `fastapi` needed to execute the backend and test suite.


## Frontend overlays

A generic modal layout is provided in `frontend/src/styles/app.css` using the
`.modal-overlay` and `.modal-box` classes. Components can use these classes to
present forms as centered overlays. Keep the modal contents narrow (max-width
around 500px) so they do not fill the entire screen on large monitors. When
opening the sighting modal from another page, pass both the ID **and** name of
the current animal and zoo in the router state. This lets the form show those
values immediately while it fetches the full lists for searching.

