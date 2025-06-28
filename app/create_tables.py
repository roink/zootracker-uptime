"""Utility to create database tables."""

from .database import engine
from .models import Base


def create_tables() -> None:
    """Create all database tables using the SQLAlchemy metadata."""
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    create_tables()

