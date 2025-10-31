"""Tests that the site-facing configuration guards produce safe defaults."""

from __future__ import annotations

from itertools import count
from importlib import util
from pathlib import Path
import sys

import pytest


_CONFIG_PATH = Path(__file__).resolve().parents[1] / "app" / "config.py"
_MODULE_COUNTER = count()


def _load_config_module():
    """Load ``app.config`` under a temporary module name using current env."""

    module_name = f"_test_app_config_{next(_MODULE_COUNTER)}"
    spec = util.spec_from_file_location(module_name, _CONFIG_PATH)
    module = util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    sys.modules[module_name] = module
    try:
        loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    return module


async def test_site_base_url_defaults_to_app_base_url(client, monkeypatch):
    monkeypatch.setenv("APP_BASE_URL", "https://frontend.example")
    monkeypatch.delenv("SITE_BASE_URL", raising=False)

    module = _load_config_module()

    assert module.SITE_BASE_URL == "https://frontend.example"
    assert module.SITE_BASE_URL == module.APP_BASE_URL


async def test_site_languages_default(client, monkeypatch):
    monkeypatch.delenv("SITE_LANGUAGES", raising=False)

    module = _load_config_module()

    assert module.SITE_LANGUAGES == ("en", "de")
    assert module.SITE_DEFAULT_LANGUAGE == "en"


@pytest.mark.parametrize("value", ["", "en_US"])
async def test_invalid_site_languages_raise(client, monkeypatch, value):
    monkeypatch.setenv("SITE_BASE_URL", "https://frontend.example")
    monkeypatch.setenv("SITE_LANGUAGES", value)

    module_name = f"_test_app_config_invalid_{next(_MODULE_COUNTER)}"
    spec = util.spec_from_file_location(module_name, _CONFIG_PATH)
    module = util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    sys.modules[module_name] = module
    try:
        with pytest.raises(RuntimeError):
            loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)


async def test_site_base_url_must_be_absolute(client, monkeypatch):
    monkeypatch.setenv("SITE_BASE_URL", "//relative-path")

    module_name = f"_test_app_config_bad_url_{next(_MODULE_COUNTER)}"
    spec = util.spec_from_file_location(module_name, _CONFIG_PATH)
    module = util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    sys.modules[module_name] = module
    try:
        with pytest.raises(RuntimeError):
            loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
