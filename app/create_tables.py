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
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_sightings_user_day_created "
                "ON animal_sightings (user_id, sighting_datetime DESC, created_at DESC)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_sightings_user_zoo_datetime "
                "ON animal_sightings (user_id, zoo_id, sighting_datetime DESC, created_at DESC)"
            )
        )
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
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_zoos_country_id ON zoos (country_id)")
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_zoos_continent_id ON zoos (continent_id)"
            )
        )
        conn.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS idx_zoos_slug ON zoos (slug)")
        )


if __name__ == "__main__":
    create_tables()

