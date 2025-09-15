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
                    "CREATE INDEX IF NOT EXISTS idx_sightings_user_day_created "
                    "ON animal_sightings (user_id, (CAST(sighting_datetime AS date)), created_at DESC)"
                )
            )
        else:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_sightings_user_day_created "
                    "ON animal_sightings (user_id, date(sighting_datetime), created_at DESC)"
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
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_zoos_country_id ON zoos (country_id)")
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_zoos_continent_id ON zoos (continent_id)"
            )
        )


if __name__ == "__main__":
    create_tables()

