"""Tests for environment-driven API settings and the module entrypoint."""

from __future__ import annotations

import pytest
import uvicorn

from sales_api import __main__ as entrypoint
from sales_api.settings import (
    DEFAULT_GZIP_MIN_SIZE,
    DEFAULT_MAX_SESSIONS,
    DEFAULT_SESSION_TTL_SECONDS,
    ApiSettings,
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "SALES_API_SESSION_TTL_SECONDS",
        "SALES_API_MAX_SESSIONS",
        "SALES_API_CORS_ORIGINS",
        "SALES_API_HOST",
        "SALES_API_PORT",
        "SALES_API_STATIC_DIR",
        "SALES_API_ENABLE_DOCS",
        "SALES_API_GZIP_MIN_SIZE",
        "SALES_API_SECURITY_HEADERS",
    ):
        monkeypatch.delenv(name, raising=False)


def test_defaults_are_used_when_nothing_is_set() -> None:
    settings = ApiSettings.from_env()

    assert settings.session_ttl_seconds == DEFAULT_SESSION_TTL_SECONDS
    assert settings.max_sessions == DEFAULT_MAX_SESSIONS
    assert settings.cors_origins == ()


def test_valid_overrides_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SALES_API_SESSION_TTL_SECONDS", "120")
    monkeypatch.setenv("SALES_API_MAX_SESSIONS", "7")
    monkeypatch.setenv(
        "SALES_API_CORS_ORIGINS",
        "http://localhost:5173, https://example.com ,",
    )

    settings = ApiSettings.from_env()

    assert settings.session_ttl_seconds == 120
    assert settings.max_sessions == 7
    assert settings.cors_origins == ("http://localhost:5173", "https://example.com")


@pytest.mark.parametrize("value", ["not-a-number", "0", "-3", ""])
def test_invalid_numbers_fall_back_to_defaults(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("SALES_API_SESSION_TTL_SECONDS", value)
    monkeypatch.setenv("SALES_API_MAX_SESSIONS", value)

    settings = ApiSettings.from_env()

    assert settings.session_ttl_seconds == DEFAULT_SESSION_TTL_SECONDS
    assert settings.max_sessions == DEFAULT_MAX_SESSIONS


def test_frontend_serving_defaults_are_enabled() -> None:
    settings = ApiSettings.from_env()

    assert settings.enable_docs is True
    assert settings.gzip_min_size == DEFAULT_GZIP_MIN_SIZE
    assert settings.security_headers is True


def test_static_and_frontend_overrides_are_read(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("SALES_API_STATIC_DIR", str(tmp_path))
    monkeypatch.setenv("SALES_API_ENABLE_DOCS", "false")
    monkeypatch.setenv("SALES_API_GZIP_MIN_SIZE", "0")
    monkeypatch.setenv("SALES_API_SECURITY_HEADERS", "off")

    settings = ApiSettings.from_env()

    assert settings.static_dir == tmp_path
    assert settings.enable_docs is False
    assert settings.gzip_min_size == 0
    assert settings.security_headers is False


@pytest.mark.parametrize("value", ["not-a-number", "-1"])
def test_invalid_gzip_size_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("SALES_API_GZIP_MIN_SIZE", value)

    settings = ApiSettings.from_env()

    assert settings.gzip_min_size == DEFAULT_GZIP_MIN_SIZE


def test_entrypoint_passes_configuration_to_uvicorn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_run(app: str, **kwargs: object) -> None:
        calls["app"] = app
        calls.update(kwargs)

    monkeypatch.setattr(uvicorn, "run", fake_run)
    monkeypatch.setenv("SALES_API_HOST", "0.0.0.0")
    monkeypatch.setenv("SALES_API_PORT", "9123")

    entrypoint.main()

    assert calls == {
        "app": "sales_api.app:app",
        "host": "0.0.0.0",
        "port": 9123,
        "reload": False,
    }


def test_entrypoint_falls_back_to_the_default_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: calls.update(kwargs))
    monkeypatch.setenv("SALES_API_PORT", "not-a-port")

    entrypoint.main()

    assert calls["port"] == 8000
