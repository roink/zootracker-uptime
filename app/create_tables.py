"""Utility to create database tables."""

from .database import engine
from .models import Base
from .triggers import create_triggers
from .db_extensions import ensure_pg_extensions
from sqlalchemy import text


def create_tables() -> None:
    """Create all database tables using the SQLAlchemy metadata."""
    ensure_pg_extensions(engine)
    Base.metadata.create_all(bind=engine)
    create_triggers(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_zooanimal_animal_id ON zoo_animals (animal_id)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_zooanimal_zoo_id ON zoo_animals (zoo_id)"
            )
        )
        if engine.dialect.name == "postgresql":
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_zoos_location_gist ON zoos USING GIST (location)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_zoos_name_trgm ON zoos USING GIN (name gin_trgm_ops)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_zoos_city_trgm ON zoos USING GIN (city gin_trgm_ops)"
                )
            )


if __name__ == "__main__":
    create_tables()

