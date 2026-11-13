"""Keep the package, app config and build metadata on the same version."""

import tomllib
from pathlib import Path

from sales_dashboard import __version__
from sales_dashboard.config import APP_VERSION

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_versions_match_pyproject() -> None:
    metadata = tomllib.loads((_PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert __version__ == APP_VERSION == metadata["project"]["version"]
