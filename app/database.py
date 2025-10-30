"""Database configuration used across the application."""

import os
import warnings
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# Connection string for the PostgreSQL database.  A value **must** be provided
# via the ``DATABASE_URL`` environment variable so deployments never rely on
# an implicit insecure default.
DATABASE_URL = os.getenv("DATABASE_URL")
APP_ENV = os.getenv("APP_ENV", "production").lower()

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is required to connect to PostgreSQL"
    )

PLACEHOLDER_PREFIXES = (
    "postgresql://postgres:postgres@",
    "postgresql+psycopg://postgres:postgres@",
)


def _uses_placeholder(url: str) -> bool:
    """Return True when the connection URL uses the legacy postgres:postgres pair."""

    return any(url.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES)


if APP_ENV == "production" and _uses_placeholder(DATABASE_URL):
    raise RuntimeError(
        "Refusing to start in production with the legacy postgres:postgres placeholder in DATABASE_URL."
    )
if _uses_placeholder(DATABASE_URL):
    warnings.warn(
        "DATABASE_URL appears to use the 'postgres:postgres' placeholder. "
        "This is acceptable for local development and tests but must not be used in production.",
        RuntimeWarning,
        stacklevel=2,
    )

# Global engine and session factory used by the application.  Zoo Tracker relies
# on PostgreSQL/PostGIS; fail fast if another backend is configured.
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,  # refresh dead/stale conns automatically
    future=True,
)
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
