from sqlalchemy import text


def ensure_pg_extensions(engine) -> None:
    if engine.dialect.name != "postgresql":
        raise RuntimeError("PostgreSQL/PostGIS is required")
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

