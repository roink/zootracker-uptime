"""Tests for database URL validation on startup."""

import importlib
import os
import warnings

import pytest

try:
    import app.database as database_module
except ModuleNotFoundError as exc:  # pragma: no cover - dependency guard
    if exc.name == "psycopg":
        pytest.skip("psycopg driver not installed", allow_module_level=True)
    raise


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


@pytest.mark.parametrize(
    ("url", "requires_psycopg"),
    [
        ("postgresql://postgres:postgres@localhost:5432/postgres", True),
        ("postgresql+psycopg://postgres:postgres@localhost:5432/postgres", True),
        (
            "postgresql+psycopg_async://postgres:postgres@localhost:5432/postgres",
            True,
        ),
    ],
)
def test_placeholder_allowed_in_dev(monkeypatch, url, requires_psycopg):
    """Explicit placeholder URLs are tolerated for development/test environments."""

    if requires_psycopg:
        pytest.importorskip("psycopg")

    original_url = os.environ.get("DATABASE_URL")
    original_env = os.environ.get("APP_ENV")

    try:
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("DATABASE_URL", url)

        # Should not raise during reload in development.
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            importlib.reload(database_module)

        assert any(w.category is RuntimeWarning for w in caught)
    finally:
        _restore_env(monkeypatch, "DATABASE_URL", original_url)
        _restore_env(monkeypatch, "APP_ENV", original_env)
        importlib.reload(database_module)


@pytest.mark.parametrize(
    ("url", "requires_psycopg"),
    [
        ("postgresql://postgres:postgres@localhost:5432/postgres", True),
        ("postgresql+psycopg://postgres:postgres@localhost:5432/postgres", True),
        (
            "postgresql+psycopg_async://postgres:postgres@localhost:5432/postgres",
            True,
        ),
    ],
)
def test_placeholder_blocked_in_production(monkeypatch, url, requires_psycopg):
    """Production environments should refuse the historical placeholder credentials."""

    if requires_psycopg:
        pytest.importorskip("psycopg")

    original_url = os.environ.get("DATABASE_URL")
    original_env = os.environ.get("APP_ENV")

    try:
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("DATABASE_URL", url)

        with pytest.raises(RuntimeError, match="Refusing to start in production"):
            importlib.reload(database_module)
    finally:
        _restore_env(monkeypatch, "DATABASE_URL", original_url)
        _restore_env(monkeypatch, "APP_ENV", original_env)
        importlib.reload(database_module)


def test_placeholder_detection_ignores_non_prefix_occurrences(monkeypatch):
    """Do not flag URLs that contain the substring outside of the credentials."""
    original_url = os.environ.get("DATABASE_URL")
    original_env = os.environ.get("APP_ENV")

    try:
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql://valid:password@localhost:5432/postgres?note=postgres:postgres",
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            importlib.reload(database_module)

        assert not any(w.category is RuntimeWarning for w in caught)
    finally:
        _restore_env(monkeypatch, "DATABASE_URL", original_url)
        _restore_env(monkeypatch, "APP_ENV", original_env)
        importlib.reload(database_module)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://zoo:zoo@localhost:5432/zoo",
        "postgresql+psycopg://zoo:zoo@localhost:5432/zoo",
        "postgresql+psycopg_async://zoo:zoo@localhost:5432/zoo",
    ],
)
def test_urls_are_normalised_to_expected_drivers(url):
    async_url = database_module._normalise_async_url(url)
    sync_url = database_module._normalise_sync_url(url)

    assert async_url.drivername == "postgresql+psycopg_async"
    assert sync_url.drivername == "postgresql+psycopg"
