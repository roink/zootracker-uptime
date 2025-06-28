# Agent Instructions

This repository provides a FastAPI backend for tracking zoo visits and animal sightings. It uses a PostgreSQL database and includes a demo frontend served separately.

## Running the application

The recommended way to start the API is with Docker Compose:

```bash
docker compose up --build
```

The API server will listen on `http://localhost:8000`.

If you need to initialize the database schema manually, run:

```bash
docker compose exec app python -m app.create_tables
```

## Running tests

Use the provided Docker Compose environment for tests. Start the services and execute pytest in the app container:

```bash
docker compose up --build -d
 docker compose exec app python -m pytest
```

Always run the tests after making changes.

