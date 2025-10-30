from sqlalchemy import text
from sqlalchemy.engine import Engine


def ensure_pg_extensions(engine: Engine) -> None:
    if engine.dialect.name != "postgresql":
        raise RuntimeError("PostgreSQL/PostGIS is required")
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        conn.execute(
            text(
                """
                CREATE OR REPLACE FUNCTION f_unaccent(text)
                RETURNS text
                LANGUAGE sql IMMUTABLE PARALLEL SAFE AS
                $$ SELECT public.unaccent('public.unaccent', $1) $$
                """
            )
        )

