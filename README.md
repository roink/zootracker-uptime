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
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000` and the database listens on `localhost:5432`.
These commands create the tables and enable the required `postgis` extension.
You can verify the connection with a quick Python shell:

```python
from app.database import SessionLocal
from app import models
session = SessionLocal()
print(session.query(models.Zoo).all())
```


### Running Tests

Start the database and run the test suite against PostgreSQL:

```bash
docker compose up -d db
pytest
```

Running tests against PostgreSQL will drop and recreate all tables to ensure a
clean state. The old `--pg` flag is still accepted but no longer required.

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

Customize the map appearance by providing a tile style URL:

```
VITE_MAP_STYLE_URL=https://tiles.openfreemap.org/styles/liberty
```

If unset the frontend falls back to the OpenFreeMap "liberty" tiles.

### Internationalization

The frontend supports English and German. Routes are prefixed with the language code (e.g. `/en/animals`). Translations live in `frontend/src/locales`. See [docs/i18n.md](docs/i18n.md) for details on adding or updating strings.

### Authentication

The `/auth/login` endpoint includes the authenticated user’s `user_id` in the
JSON response so clients can identify the user without an extra lookup.
Authorization checks on the sighting endpoints ensure each user may only read,
update, or delete their own records without privileged overrides.

See [docs/auth.md](docs/auth.md) for details on configuring the rotating
refresh-token flow in development (localhost) and in production deployments.

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

### Structured Logging & Observability

Backend logs are emitted in [ECS](https://www.elastic.co/guide/en/ecs/current/index.html)
compatible JSON so they can be shipped directly into Elastic, Loki or other
machine parsers. A single configuration drives Gunicorn, Uvicorn and the
application loggers which means **all** events share the same structure and
request identifiers. Key fields include `@timestamp`, `log.level`,
`http.request.method`, `url.path`, `http.response.status_code`,
`event.duration` (nanoseconds), `client.ip`, `user.id`, and `http.request.id`.
Authentication and audit events add `authentication.method`,
`authentication.outcome.reason` and `event.kind=audit` respectively.

Configure logging behaviour with environment variables:

| Variable | Description |
| --- | --- |
| `LOG_LEVEL` | Global log level (default `INFO`). |
| `LOG_JSON` | Toggle JSON formatting (`true` by default). |
| `LOG_FILE_ANON` | Optional anonymized log file path (ECS JSON, rewrites `client.ip` to `/24` or `/64`). |
| `LOG_FILE_RAW` | Optional raw log file path that always retains the full client IP for security forensics. |
| `LOG_FILE` | Legacy single-log fallback when you only need one file sink. |
| `ACCESS_LOG_SAMPLE` | Fraction of 2xx/3xx requests to log (default `1.0`). |
| `SLOW_REQUEST_MS` | Always log requests slower than this threshold (default `500`). |
| `LOG_IP_MODE` | `full`, `anonymized` (/24 or /64) or `off` to drop client IPs. |

Sensitive headers such as `Authorization` and `Cookie` are redacted automatically
and long payloads are truncated to keep entries GDPR-friendly. When the service
runs behind Nginx and Cloudflare the middleware trusts `request.client.host`
(`real_ip_header CF-Connecting-IP`) and consults only the left-most value of
`X-Forwarded-For` for connections that originate from private proxy ranges.
Cloudflare-specific headers are intentionally ignored because Nginx already
normalises the client address. Choose `LOG_IP_MODE=anonymized` in regions where
full IP addresses are considered personal data; anonymized addresses are emitted
as `/24` (IPv4) or `/64` (IPv6) network prefixes. When both `LOG_FILE_ANON` and
`LOG_FILE_RAW` are configured the anonymized file honours those prefixes while
the raw file keeps the exact IP regardless of `LOG_IP_MODE` so you can retain a
short-lived forensic trail alongside long-term privacy-preserving analytics.

All file sinks use a `WatchedFileHandler`, which plays nicely with system-wide
rotation tools such as `logrotate`. The handler recreates files automatically
after rotation and forces restrictive `0600` permissions so only the service
user (and privileged administrators) can read historical logs.

### CORS Origins

The API only responds to cross-origin requests from whitelisted domains. Set
the `ALLOWED_ORIGINS` environment variable to a comma separated list of allowed
origins. For example, during local development:

```
ALLOWED_ORIGINS=http://localhost:5173
```

In production provide your public domains, such as:

```
ALLOWED_ORIGINS=https://zootracker.app,https://admin.zootracker.app
```

Requests from other origins will fail CORS preflight checks and browsers will
block access to the API.

### Animals API

`GET /animals` now returns detailed animal information including scientific
name, category and image URL. The endpoint accepts `limit` and `offset`
parameters for pagination so clients can request results in smaller batches.
Results are sorted by English name for stable paging and can be further
filtered by `q` and an optional `category` name. `limit` must be between 1 and
100 and `offset` cannot be negative:

```http
GET /animals?limit=20&offset=0
```

Providing a search query via `q` filters the results by English or German name. Each page
contains at most `limit` records and an empty response indicates there are no
more animals.

### Password Requirements

When registering a new account the API enforces a minimum password length of
eight characters. Submitting a shorter password will result in a 422 validation
error.

### Importing data from a SQLite dump

Use ``app/import_simple_sqlite_data.py`` to populate the database from a
SQLite dataset with a minimal schema:

```bash
python -m app.import_simple_sqlite_data path/to/data.db
```

## Production Security Notes

The API now refuses to start unless `SECRET_KEY` is defined. Supply a long,
random value before booting the service—`openssl rand -hex 32` is a convenient
way to generate a 64-character (32-byte) hex string. Weak or short secrets make
HS256 JWTs trivial to brute-force, so avoid anything guessable or reused.

When running the API on the public internet remember to:

- Serve all traffic over **HTTPS** to protect credentials and tokens.
- Regularly apply operating system and dependency updates.
- Enable rate limiting (for example via a reverse proxy) to prevent abuse.
- Keep JWT verification pinned to the expected algorithm (`algorithms=["HS256"]`)
  to avoid algorithm-confusion attacks.
- Load environment variables through your process manager (for example,
  `uvicorn app.main:app --reload --env-file .env` locally or `EnvironmentFile=/opt/zoo_tracker/.env`
  in systemd) instead of calling `load_dotenv()` in application modules.

### SECRET_KEY requirements

- **Minimum:** 32 bytes for HS256 (per RFC 7518). That corresponds to at least
  64 hexadecimal characters or roughly 43 URL-safe Base64 characters.
- Preferred formats: hex (`openssl rand -hex 32`) or URL-safe Base64
  (`python -c "import secrets; print(secrets.token_urlsafe(32))"`).
- **Never reuse** the same key across environments (production, staging,
  development). Generate a new one for each deployment.

