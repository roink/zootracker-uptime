"""Database configuration used across the application."""

import os
import warnings
from collections.abc import AsyncGenerator, Generator

from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Connection string for the PostgreSQL database.  A value **must** be provided
# via the ``DATABASE_URL`` environment variable so deployments never rely on
# an implicit insecure default.
RAW_DATABASE_URL = os.getenv("DATABASE_URL")
APP_ENV = os.getenv("APP_ENV", "production").lower()

if not RAW_DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is required to connect to PostgreSQL"
    )


def _normalise_database_url(url: str) -> str:
    """Upgrade legacy PostgreSQL URLs to the psycopg async scheme."""

    legacy_prefixes = (
        "postgresql+psycopg://",
        "postgresql://",
    )
    for prefix in legacy_prefixes:
        if url.startswith(prefix):
            replacement = "postgresql+psycopg_async://"
            normalised = replacement + url[len(prefix) :]
            warnings.warn(
                "DATABASE_URL uses a synchronous PostgreSQL driver. "
                "Automatically switching to the psycopg async driver; "
                "update the environment to use 'postgresql+psycopg_async'.",
                RuntimeWarning,
                stacklevel=2,
            )
            return normalised
    return url


DATABASE_URL = _normalise_database_url(RAW_DATABASE_URL)

if not DATABASE_URL.startswith("postgresql+psycopg_async://"):
    raise RuntimeError(
        "Zoo Tracker now requires the psycopg async driver. "
        "Set DATABASE_URL to use the 'postgresql+psycopg_async' scheme.",
    )

PLACEHOLDER_PREFIXES = (
    "postgresql://postgres:postgres@",
    "postgresql+psycopg://postgres:postgres@",
    "postgresql+psycopg_async://postgres:postgres@",
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
async_engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
)
engine = async_engine.sync_engine
if engine.dialect.name != "postgresql":  # pragma: no cover - defensive guardrail
    raise RuntimeError("Zoo Tracker requires a PostgreSQL/PostGIS database")

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    autoflush=False,
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


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session for handlers running in the event loop."""

    async with AsyncSessionLocal() as session:
        yield session
