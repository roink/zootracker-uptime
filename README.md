# Zoo Tracker Server

This repository contains planning materials and a basic backend scaffold for the Zoo Visit and Animal Tracking service. Documentation for the architecture and user stories can be found in the `docs/` directory. The initial PostgreSQL schema is located in `schema.sql`.

## Development

A `docker-compose.yml` file is provided to run a Postgres database and the FastAPI backend. The backend is configured via the `DATABASE_URL` environment variable to connect to the database service.

### Local Setup

```bash
# create virtual environment and install dependencies
./setup_env.sh

# run services
docker compose up --build
```

The API will be available at `http://localhost:8000` and the database listens on `localhost:5432`.
