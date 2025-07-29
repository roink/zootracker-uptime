"""Utility to create database tables."""

from .database import engine
from .models import Base
from .triggers import create_triggers
from sqlalchemy import text


def create_tables() -> None:
    """Create all database tables using the SQLAlchemy metadata."""
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    Base.metadata.create_all(bind=engine)
    create_triggers(engine)


if __name__ == "__main__":
    create_tables()

