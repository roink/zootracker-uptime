# Zoo Tracker Server

This repository contains planning materials and a basic backend scaffold for the Zoo Visit and Animal Tracking service. Documentation for the architecture and user stories can be found in the `docs/` directory. The initial PostgreSQL schema is located in `schema.sql`.

## Development

A `docker-compose.yml` file is provided to run a PostGIS-enabled PostgreSQL
database and the FastAPI backend. The backend is configured via the
`DATABASE_URL` environment variable to connect to the database service.

### Local Setup

```bash
# create virtual environment and install dependencies
./setup_env.sh

# run services
docker compose up --build
```

The API will be available at `http://localhost:8000` and the database listens on `localhost:5432`.

### Database Initialization

Run the table creation script once before starting the API. This will also
enable the required `postgis` extension and create a spatial index on the
`zoos.location` column:

```bash
python -m app.create_tables
```

### Loading Example Data

CSV files with sample records for all tables are provided under `example_data/`.
The loader will create any missing tables automatically and populate the
geography column for zoos, so you can simply run:

```bash
python -m app.load_example_data
```

This inserts around 10 zoos, 20 animals and users, as well as related
records for visits, sightings and achievements. The data is useful for
local testing and development.

To verify the connection you can open a Python shell:

```python
from app.database import SessionLocal
from app import models
session = SessionLocal()
print(session.query(models.Zoo).all())
```

### Running Tests

The test suite uses SQLite by default so it can run without external services:

```bash
pytest
```

Tests that require PostgreSQL are marked with `@pytest.mark.postgres` and are
skipped unless explicitly enabled. To run the full set locally, start the
database and point `DATABASE_URL` at it before invoking pytest:

```bash
docker compose up -d db
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres
pytest --pg
```

### Running the Frontend

The frontend uses [Vite](https://vitejs.dev/) during development. Install the
dependencies once and start the dev server:

```bash
cd frontend
npm install
npm run dev
```

Vite will serve the application on <http://localhost:5173> by default with the
correct CORS and MIME headers so it can communicate with the API on port
`8000`.

When using `--host` the frontend automatically sends requests to the same
hostname on port `8000`. This means testing from a phone generally works out of
the box as long as the backend port is reachable. You can still override the API
location if needed:

```bash
VITE_API_URL=http://192.168.1.29:8000 npm run dev -- --host
```

Replace `192.168.1.29` with your computer's actual IP if it differs. Setting
`VITE_API_URL` is only required when the backend runs on a different host or
port.

### Password Requirements

When registering a new account the API enforces a minimum password length of
eight characters. Submitting a shorter password will result in a 422 validation
error.

## Production Security Notes

The default connection string in `app/database.py` uses the credentials
`postgres:postgres` and `app/main.py` falls back to the secret key `"secret"`.
These are provided strictly for local development so the application works
out of the box. **Change both values for any production deployment** by
setting the `DATABASE_URL` and `SECRET_KEY` environment variables to strong
unique values.

When running the API on the public internet remember to:

- Serve all traffic over **HTTPS** to protect credentials and tokens.
- Regularly apply operating system and dependency updates.
- Enable rate limiting (for example via a reverse proxy) to prevent abuse.

