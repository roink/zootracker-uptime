"""Tests for database URL validation on startup."""

import importlib
import os

import pytest

import app.database as database_module


@pytest.mark.parametrize(
    "bad_url",
    [None, "postgresql://postgres:postgres@localhost:5432/postgres"],
)
def test_startup_fails_without_secure_database_url(monkeypatch, bad_url):
    """The application should refuse to start without explicit secure credentials."""
    original_url = os.environ.get("DATABASE_URL")

    try:
        if bad_url is None:
            monkeypatch.delenv("DATABASE_URL", raising=False)
        else:
            monkeypatch.setenv("DATABASE_URL", bad_url)

        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            importlib.reload(database_module)
    finally:
        if original_url is None:
            monkeypatch.delenv("DATABASE_URL", raising=False)
        else:
            monkeypatch.setenv("DATABASE_URL", original_url)
        importlib.reload(database_module)
