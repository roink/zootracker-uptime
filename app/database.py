"""Database configuration used across the application."""

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# Connection string for the PostgreSQL database.  A default is provided for
# local development/testing but can be overridden via an environment variable.
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
)

# Global engine and session factory used by the application.  Zoo Tracker relies
# on PostgreSQL/PostGIS; fail fast if another backend is configured.
engine = create_engine(DATABASE_URL)
if engine.dialect.name != "postgresql":  # pragma: no cover - defensive guardrail
    raise RuntimeError("Zoo Tracker requires a PostgreSQL/PostGIS database")

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)

# Base class for all ORM models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Provide a database session for a single request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
