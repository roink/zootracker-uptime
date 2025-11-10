"""Database configuration used across the application."""

import os
import warnings
from collections.abc import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# Connection string for the PostgreSQL database.  A value **must** be provided
# via the ``DATABASE_URL`` environment variable so deployments never rely on
# an implicit insecure default.
RAW_DATABASE_URL = os.getenv("DATABASE_URL")
APP_ENV = os.getenv("APP_ENV", "production").lower()

if not RAW_DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is required to connect to PostgreSQL"
    )

_ASYNC_DRIVER = "postgresql+psycopg_async"
_SYNC_DRIVER = "postgresql+psycopg"
_ACCEPTED_DRIVERS = {"postgresql", _SYNC_DRIVER, _ASYNC_DRIVER}


def _parse_postgres_url(url: str) -> URL:
    candidate = make_url(url)
    if candidate.drivername not in _ACCEPTED_DRIVERS:
        raise RuntimeError(
            "Zoo Tracker requires a PostgreSQL connection string using the "
            "'postgresql', 'postgresql+psycopg', or 'postgresql+psycopg_async' driver."
        )
    return candidate


def _normalise_async_url(url: str) -> URL:
    """Return a URL configured for the psycopg async driver."""

    parsed = _parse_postgres_url(url)
    if parsed.drivername != _ASYNC_DRIVER:
        warnings.warn(
            "DATABASE_URL uses a synchronous PostgreSQL driver. Automatically "
            "switching to the psycopg async driver; update the environment to "
            "use 'postgresql+psycopg_async'.",
            UserWarning,
            stacklevel=2,
        )
    return parsed.set(drivername=_ASYNC_DRIVER)


def _normalise_sync_url(url: str) -> URL:
    """Return a URL configured for the psycopg sync driver."""

    parsed = _parse_postgres_url(url)
    return parsed.set(drivername=_SYNC_DRIVER)


ASYNC_DATABASE_URL = _normalise_async_url(RAW_DATABASE_URL)
SYNC_DATABASE_URL = _normalise_sync_url(RAW_DATABASE_URL)
# SQLAlchemy obscures passwords when coercing ``URL`` objects to strings via
# ``str(url)``.  Use ``render_as_string`` so downstream consumers (including the
# engine itself) receive the real credentials instead of ``***`` which would
# cause authentication to fail.
DATABASE_URL = ASYNC_DATABASE_URL.render_as_string(hide_password=False)


def _render_url(url: str | URL) -> str:
    return url if isinstance(url, str) else url.render_as_string(hide_password=False)


def make_sync_engine(url: str | URL) -> Engine:
    """Return a synchronous Engine for a potentially async connection URL."""

    sync_url = _normalise_sync_url(_render_url(url))
    return create_engine(sync_url)

def _uses_placeholder(url: URL) -> bool:
    """Return True when the connection URL uses the legacy postgres:postgres pair."""

    return bool(url.username == "postgres" and url.password == "postgres")  # noqa: S105


if APP_ENV == "production" and _uses_placeholder(ASYNC_DATABASE_URL):
    raise RuntimeError(
        "Refusing to start in production with the legacy postgres:postgres placeholder in DATABASE_URL."
    )
if _uses_placeholder(ASYNC_DATABASE_URL):
    warnings.warn(
        "DATABASE_URL appears to use the 'postgres:postgres' placeholder. "
        "This is acceptable for local development and tests but must not be used in production.",
        RuntimeWarning,
        stacklevel=2,
    )

# Global engine and session factory used by the application.  Zoo Tracker relies
# on PostgreSQL/PostGIS; fail fast if another backend is configured.
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
)
engine = make_sync_engine(SYNC_DATABASE_URL)
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
