"""Tests for database URL validation on startup."""

import importlib
import os

import pytest

import app.database as database_module


def _restore_env(monkeypatch, key, value):
    if value is None:
        monkeypatch.delenv(key, raising=False)
    else:
        monkeypatch.setenv(key, value)


def test_startup_fails_when_database_url_missing(monkeypatch):
    """App must fail to start if DATABASE_URL is not set at all."""
    original_url = os.environ.get("DATABASE_URL")
    original_env = os.environ.get("APP_ENV")

    try:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("APP_ENV", raising=False)

        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            importlib.reload(database_module)
    finally:
        _restore_env(monkeypatch, "DATABASE_URL", original_url)
        _restore_env(monkeypatch, "APP_ENV", original_env)
        importlib.reload(database_module)


def test_insecure_placeholder_allowed_in_dev(monkeypatch):
    """Explicit placeholder URL is tolerated for development/test environments."""
    original_url = os.environ.get("DATABASE_URL")
    original_env = os.environ.get("APP_ENV")

    try:
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/postgres",
        )

        # Should not raise during reload in development.
        importlib.reload(database_module)
    finally:
        _restore_env(monkeypatch, "DATABASE_URL", original_url)
        _restore_env(monkeypatch, "APP_ENV", original_env)
        importlib.reload(database_module)


def test_insecure_placeholder_blocked_in_production(monkeypatch):
    """Production environments should refuse the historical placeholder."""
    original_url = os.environ.get("DATABASE_URL")
    original_env = os.environ.get("APP_ENV")

    try:
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/postgres",
        )

        with pytest.raises(RuntimeError, match="Refusing to start in production"):
            importlib.reload(database_module)
    finally:
        _restore_env(monkeypatch, "DATABASE_URL", original_url)
        _restore_env(monkeypatch, "APP_ENV", original_env)
        importlib.reload(database_module)
