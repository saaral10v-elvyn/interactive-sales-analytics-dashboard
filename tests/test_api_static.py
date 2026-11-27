"""Tests for serving the built React SPA alongside the API."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sales_api.app import create_app
from sales_api.sessions import SessionStore
from sales_api.settings import ApiSettings

INDEX_HTML = (
    '<!doctype html><html><body><div id="root"></div>'
    '<script type="module" src="/assets/app-abc123.js"></script></body></html>'
)
APP_JS = "console.log('sales dashboard');\n" * 100
FAVICON = '<svg xmlns="http://www.w3.org/2000/svg"></svg>'


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    """A minimal build directory shaped like Vite's output."""
    directory = tmp_path / "dist"
    assets = directory / "assets"
    assets.mkdir(parents=True)
    (directory / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (directory / "favicon.svg").write_text(FAVICON, encoding="utf-8")
    (assets / "app-abc123.js").write_text(APP_JS, encoding="utf-8")
    return directory


@pytest.fixture
def client(dist: Path) -> TestClient:
    app = create_app(
        ApiSettings(static_dir=dist),
        SessionStore(ttl_seconds=60, max_sessions=5),
    )
    with TestClient(app) as test_client:
        yield test_client


def test_root_serves_the_spa(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<div id="root"></div>' in response.text
    assert response.headers["cache-control"] == "no-cache"


@pytest.mark.parametrize(
    "path",
    ["/prepare", "/overview", "/products", "/regions", "/explorer", "/some/client/route"],
)
def test_client_routes_fall_back_to_index(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 200
    assert '<div id="root"></div>' in response.text
    assert response.headers["cache-control"] == "no-cache"


def test_hashed_assets_are_cached_forever(client: TestClient) -> None:
    response = client.get("/assets/app-abc123.js")

    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_root_files_are_served(client: TestClient) -> None:
    response = client.get("/favicon.svg")

    assert response.status_code == 200
    assert "image/svg+xml" in response.headers["content-type"]
    assert response.headers["cache-control"] == "public, max-age=3600"


def test_a_missing_asset_is_not_replaced_by_the_spa(client: TestClient) -> None:
    response = client.get("/assets/missing.js")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.parametrize("path", ["/api/not-a-route", "/exports/not-a-route", "/api", "/exports"])
def test_api_and_export_prefixes_stay_json(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_api_routes_keep_working_when_the_spa_is_served(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_a_missing_root_file_is_not_the_spa(client: TestClient) -> None:
    response = client.get("/missing.js")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_post_is_not_accepted_by_the_spa_fallback(client: TestClient) -> None:
    response = client.post("/overview")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_head_requests_are_supported(client: TestClient) -> None:
    response = client.head("/")

    assert response.status_code == 200
    assert response.content == b""


def test_a_directory_without_index_is_ignored(tmp_path: Path) -> None:
    app = create_app(
        ApiSettings(static_dir=tmp_path / "empty"),
        SessionStore(ttl_seconds=60, max_sessions=5),
    )

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_security_headers_are_attached(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "geolocation=()" in response.headers["permissions-policy"]


def test_security_headers_can_be_disabled() -> None:
    app = create_app(
        ApiSettings(security_headers=False),
        SessionStore(ttl_seconds=60, max_sessions=5),
    )

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert "x-content-type-options" not in response.headers


def test_gzip_compresses_large_json() -> None:
    app = create_app(ApiSettings(), SessionStore(ttl_seconds=60, max_sessions=5))

    with TestClient(app) as client:
        response = client.get("/api/meta", headers={"Accept-Encoding": "gzip"})

    assert response.status_code == 200
    assert response.headers.get("content-encoding") == "gzip"
    assert response.json()["app"]["version"]


def test_gzip_threshold_can_be_raised() -> None:
    app = create_app(
        ApiSettings(gzip_min_size=10**9),
        SessionStore(ttl_seconds=60, max_sessions=5),
    )

    with TestClient(app) as client:
        response = client.get("/api/meta", headers={"Accept-Encoding": "gzip"})

    assert "content-encoding" not in response.headers


def test_docs_can_be_disabled() -> None:
    app = create_app(
        ApiSettings(enable_docs=False),
        SessionStore(ttl_seconds=60, max_sessions=5),
    )

    with TestClient(app) as client:
        assert client.get("/api/openapi.json").status_code == 404
        assert client.get("/api/docs").status_code == 404
