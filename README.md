# Zoo Tracker Server

This repository contains planning materials and a basic backend scaffold for the Zoo Visit and Animal Tracking service. Documentation for the architecture and user stories can be found in the `docs/` directory. The initial PostgreSQL schema is located in `schema.sql`.

## Development

A `docker-compose.yml` file is provided to run a PostGIS-enabled PostgreSQL
database. Start the API separately with Uvicorn using the `DATABASE_URL`
environment variable to connect.

### Local Setup

```bash
./setup_env.sh
cp .env.example .env
docker compose up -d db
python -m app.create_tables
python -m app.load_example_data
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000` and the database listens on `localhost:5432`.
These commands create the tables, enable the required `postgis` extension and
insert sample records from `example_data/`. You can verify the connection with a
quick Python shell:

```python
from app.database import SessionLocal
from app import models
session = SessionLocal()
print(session.query(models.Zoo).all())
```


### Running Tests

Start the database and run the PostgreSQL tests:

```bash
docker compose up -d db
pytest --pg
```

Running tests against PostgreSQL will drop and recreate all tables to ensure a
clean state. You can still run a fast subset with SQLite using `pytest` alone.

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

### Contact Form Email

The `/contact` endpoint sends messages via SMTP using credentials from
environment variables. Provide them in a `.env` file or your shell before
starting the server:

```
SMTP_HOST=smtppro.zoho.com
SMTP_PORT=465
SMTP_SSL=true
SMTP_USER=username
SMTP_PASSWORD=password
SMTP_FROM=contact@zootracker.app
CONTACT_EMAIL=contact@zootracker.app
CONTACT_RATE_LIMIT=5
```

Set `SMTP_SSL=true` when your provider requires an SSL connection (such as Zoho
on port 465); otherwise the server will use STARTTLS.

The visitor's address is included as the `Reply-To` header and the subject line
uses their name (e.g. "Contact form – Alice"). `CONTACT_RATE_LIMIT` controls
how many submissions are accepted per minute from a single IP. The server checks
for `SMTP_HOST` and `CONTACT_EMAIL` at startup and will refuse to run if either
is missing. Rate-limited responses include `X-RateLimit-Remaining` and
`Retry-After` headers to aid debugging.

### Animals API

`GET /animals` now returns detailed animal information including scientific
name, category and image URL. The endpoint accepts `limit` and `offset`
parameters for pagination so clients can request results in smaller batches.
Results are sorted by common name for stable paging and can be further
filtered by `q` and an optional `category` name. `limit` must be between 1 and
100 and `offset` cannot be negative:

```http
GET /animals?limit=20&offset=0
```

Providing a search query via `q` filters the results by common name. Each page
contains at most `limit` records and an empty response indicates there are no
more animals.

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

