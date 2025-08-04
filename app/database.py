"""Database configuration used across the application."""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from typing import Generator
import uuid

# Connection string for the PostgreSQL database.  A default is provided for
# local development/testing but can be overridden via an environment variable.
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/postgres")

# Global engine and session factory used by the application
engine = create_engine(DATABASE_URL)

# Add a UUID generation function for SQLite so triggers can create IDs
if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def _sqlite_uuid(conn, record):
        conn.create_function("gen_random_uuid", 0, lambda: str(uuid.uuid4()))
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
