"""Database configuration used across the application."""

import os
import warnings
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# Connection string for the PostgreSQL database.  A value **must** be provided
# via the ``DATABASE_URL`` environment variable so deployments never rely on
# an implicit insecure default.
DATABASE_URL = os.getenv("DATABASE_URL")
APP_ENV = os.getenv("APP_ENV", "development").lower()

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is required to connect to PostgreSQL"
    )

placeholder = "postgresql://postgres:postgres@"
if APP_ENV == "production" and placeholder in DATABASE_URL:
    raise RuntimeError(
        "Refusing to start in production with the legacy postgres:postgres placeholder in DATABASE_URL."
    )
if placeholder in DATABASE_URL:
    warnings.warn(
        "DATABASE_URL appears to use the 'postgres:postgres' placeholder. "
        "This is acceptable for local development and tests but must not be used in production.",
        RuntimeWarning,
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
