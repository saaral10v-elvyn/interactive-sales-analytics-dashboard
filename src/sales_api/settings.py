"""Runtime settings for the API, read from the environment at startup."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from sales_dashboard.config import PROJECT_ROOT

DEFAULT_SESSION_TTL_SECONDS = 30 * 60
DEFAULT_MAX_SESSIONS = 100
DEFAULT_GZIP_MIN_SIZE = 1024
DEFAULT_STATIC_DIR = PROJECT_ROOT / "frontend" / "dist"


def _positive_int(name: str, default: int) -> int:
    """Read a positive integer, falling back to the default when unset or invalid."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _non_negative_int(name: str, default: int) -> int:
    """Read a zero-or-greater integer, falling back to the default when invalid."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= 0 else default


def _flag(name: str, default: bool) -> bool:
    """Read a boolean flag, accepting common true/false spellings."""
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw not in {"0", "false", "no", "off"}


def _origins(name: str) -> tuple[str, ...]:
    """Read a comma-separated CORS allow-list."""
    raw = os.environ.get(name, "")
    return tuple(origin.strip() for origin in raw.split(",") if origin.strip())


def _path(name: str) -> Path | None:
    """Read an optional filesystem path."""
    raw = os.environ.get(name, "").strip()
    return Path(raw).expanduser() if raw else None


@dataclass(frozen=True)
class ApiSettings:
    """Configuration that differs between development and deployment."""

    session_ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS
    max_sessions: int = DEFAULT_MAX_SESSIONS
    cors_origins: tuple[str, ...] = ()
    static_dir: Path | None = None
    enable_docs: bool = True
    gzip_min_size: int = DEFAULT_GZIP_MIN_SIZE
    security_headers: bool = True

    @classmethod
    def from_env(cls) -> ApiSettings:
        """Build settings from ``SALES_API_*`` variables.

        ``SALES_API_STATIC_DIR`` wins when set. Otherwise the built frontend is
        used if ``frontend/dist`` already exists, which keeps ``python -m
        sales_api`` useful after a local production build without extra flags.
        """
        static_dir = _path("SALES_API_STATIC_DIR")
        if static_dir is None and DEFAULT_STATIC_DIR.is_dir():
            static_dir = DEFAULT_STATIC_DIR

        return cls(
            session_ttl_seconds=_positive_int(
                "SALES_API_SESSION_TTL_SECONDS",
                DEFAULT_SESSION_TTL_SECONDS,
            ),
            max_sessions=_positive_int("SALES_API_MAX_SESSIONS", DEFAULT_MAX_SESSIONS),
            cors_origins=_origins("SALES_API_CORS_ORIGINS"),
            static_dir=static_dir,
            enable_docs=_flag("SALES_API_ENABLE_DOCS", True),
            gzip_min_size=_non_negative_int("SALES_API_GZIP_MIN_SIZE", DEFAULT_GZIP_MIN_SIZE),
            security_headers=_flag("SALES_API_SECURITY_HEADERS", True),
        )
