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

### Database Initialization

Run the table creation script once before starting the API:

```bash
python -m app.create_tables
```

### Loading Example Data

CSV files with sample records for all tables are provided under `example_data/`.
After creating the tables you can populate the database with this data:

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

### Running the Frontend

The demo frontend under `frontend/` must be served via HTTP. Opening
`index.html` directly with the `file://` scheme leads to CORS errors and a blank
page. Start a small web server from the directory:

```bash
# from the repository root
cd frontend
# choose a port that isn't used by FastAPI (e.g. 8080)
python -m http.server 8080
```

Then open <http://localhost:8080>. The frontend will talk to the API on port
`8000`.
