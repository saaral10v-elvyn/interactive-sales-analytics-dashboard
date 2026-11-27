"""Contract tests for the dataset lifecycle endpoints."""

from __future__ import annotations

import io
import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient

from sales_api.app import create_app
from sales_api.errors import ApiError
from sales_api.responses import NormalisedJSONResponse
from sales_api.routers import datasets
from sales_api.sessions import Session, SessionStore
from sales_api.settings import ApiSettings
from sales_api.views import session_payload
from sales_dashboard.config import APP_VERSION

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
SAMPLE_CSV = (
    b"order_id,order_date,product,category,region,quantity,unit_price,status\n"
    b"A-1,2026-01-05,Alpha Widget,Widgets,North,2,100,Completed\n"
    b"A-2,2026-01-06,Beta Widget,Widgets,South,1,50,Completed\n"
)


class FakeClock:
    def __init__(self, start: float = 1_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture(scope="module")
def store() -> SessionStore:
    return SessionStore(ttl_seconds=300, max_sessions=10)


@pytest.fixture(scope="module")
def client(store: SessionStore) -> TestClient:
    app = create_app(
        ApiSettings(session_ttl_seconds=300, max_sessions=10),
        store,
    )
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def demo(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/datasets/demo")
    assert response.status_code == 201
    return response.json()


def _upload(client: TestClient) -> dict[str, Any]:
    response = client.post(
        "/api/datasets",
        files={"file": ("sample.csv", SAMPLE_CSV, "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_health_reports_version_and_sessions(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == APP_VERSION
    assert body["active_sessions"] >= 0


def test_meta_exposes_the_upload_and_filter_contract(client: TestClient) -> None:
    body = client.get("/api/meta").json()

    assert body["app"]["version"] == APP_VERSION
    assert body["currency"]["symbol"] == "₹"
    assert {"max_upload_mb", "max_rows"} <= set(body["limits"])
    assert ".csv" in body["uploads"]["extensions"]
    assert "order_date" in body["required_fields"]
    assert body["field_order"][0] == "order_id"
    assert {field["column"] for field in body["fields"]} >= {"order_id", "order_date", "product"}
    assert body["filters"]["fields"] == ["category", "region", "product", "status"]
    assert body["filters"]["default_preset"] in {
        preset["key"] for preset in body["filters"]["presets"]
    }


def test_demo_creation_returns_a_full_dataset_summary(
    client: TestClient,
    demo: dict[str, Any],
) -> None:
    assert demo["session_id"]
    assert demo["cleaned"] is None
    assert demo["mapping_override"] == {}
    assert demo["revision"] == 0

    dataset = demo["dataset"]
    assert dataset["filename"] == "sales_demo.csv"
    assert dataset["source"] == "demo"
    assert dataset["row_count"] > 0
    assert dataset["column_count"] == len(dataset["columns"])
    assert len(dataset["preview"]) == 5
    assert dataset["mapping"]["is_complete"] is True
    assert dataset["profile"]["row_count"] == dataset["row_count"]


def test_demo_summary_matches_the_frozen_contract(demo: dict[str, Any]) -> None:
    """The API must serialise the dataset exactly like the golden fixture."""
    golden = json.loads((GOLDEN_DIR / "demo.json").read_text(encoding="utf-8"))

    assert demo["dataset"] == golden["dataset"]


def test_dataset_can_be_fetched_again(
    client: TestClient,
    demo: dict[str, Any],
) -> None:
    response = client.get(f"/api/datasets/{demo['session_id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == demo["session_id"]
    assert body["dataset"] == demo["dataset"]


def test_unknown_session_returns_a_structured_404(client: TestClient) -> None:
    response = client.get("/api/datasets/does-not-exist")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "SESSION_NOT_FOUND"
    assert error["details"]["session_id"] == "does-not-exist"


def test_delete_is_immediate_and_not_repeatable(client: TestClient) -> None:
    session_id = _upload(client)["session_id"]

    assert client.delete(f"/api/datasets/{session_id}").status_code == 204
    assert client.get(f"/api/datasets/{session_id}").status_code == 404

    second = client.delete(f"/api/datasets/{session_id}")
    assert second.status_code == 404
    assert second.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_sessions_are_isolated(client: TestClient) -> None:
    first = _upload(client)["session_id"]
    second = _upload(client)["session_id"]

    assert first != second
    assert client.delete(f"/api/datasets/{first}").status_code == 204
    assert client.get(f"/api/datasets/{first}").status_code == 404
    assert client.get(f"/api/datasets/{second}").status_code == 200


def test_upload_detects_the_schema(client: TestClient) -> None:
    body = _upload(client)

    dataset = body["dataset"]
    assert dataset["filename"] == "sample.csv"
    assert dataset["source"] == "upload"
    assert dataset["row_count"] == 2
    assert dataset["mapping"]["fields"]["order_date"] == "order_date"
    assert dataset["mapping"]["fields"]["product"] == "product"
    assert dataset["mapping"]["is_complete"] is True


def test_upload_without_a_file_is_a_validation_error(client: TestClient) -> None:
    response = client.post("/api/datasets")

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "INVALID_REQUEST"
    assert error["details"]["errors"]


def test_upload_rejects_an_unsupported_extension(client: TestClient) -> None:
    response = client.post(
        "/api/datasets",
        files={"file": ("notes.txt", SAMPLE_CSV, "text/plain")},
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "INVALID_DATASET"
    assert error["message"] == "Unsupported file type (.txt)."
    assert error["details"]["hint"]


def test_upload_rejects_an_empty_file(client: TestClient) -> None:
    response = client.post(
        "/api/datasets",
        files={"file": ("empty.csv", b"", "text/csv")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "EMPTY_UPLOAD"


def test_upload_rejects_a_missing_filename(store: SessionStore) -> None:
    upload = UploadFile(filename=None, file=io.BytesIO(SAMPLE_CSV))

    with pytest.raises(ApiError) as caught:
        datasets.upload_dataset(store, upload)

    assert caught.value.status_code == 400
    assert caught.value.code == "MISSING_FILENAME"


def test_upload_rejects_a_file_over_the_limit(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sales_api.routers.datasets.MAX_UPLOAD_BYTES", 10)

    response = client.post(
        "/api/datasets",
        files={"file": ("big.csv", SAMPLE_CSV, "text/csv")},
    )

    assert response.status_code == 413
    error = response.json()["error"]
    assert error["code"] == "UPLOAD_TOO_LARGE"
    assert error["details"]["max_upload_mb"] > 0


def test_expired_session_is_gone_over_http() -> None:
    clock = FakeClock()
    store = SessionStore(ttl_seconds=5, max_sessions=5, clock=clock)
    app = create_app(ApiSettings(), store)

    with TestClient(app) as client:
        session_id = client.post("/api/datasets/demo").json()["session_id"]
        clock.advance(5)
        response = client.get(f"/api/datasets/{session_id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_the_app_uses_the_injected_store(store: SessionStore) -> None:
    app = create_app(ApiSettings(), store)

    assert app.state.sessions is store


def test_unknown_routes_and_methods_share_the_error_envelope(client: TestClient) -> None:
    missing = client.get("/api/not-a-route")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"

    wrong_method = client.put("/api/health")
    assert wrong_method.status_code == 405
    assert wrong_method.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_openapi_document_describes_the_routes(client: TestClient) -> None:
    response = client.get("/api/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/health" in paths
    assert "/api/datasets" in paths
    assert "/api/datasets/demo" in paths


def test_configured_origins_get_cors_headers() -> None:
    app = create_app(
        ApiSettings(cors_origins=("http://localhost:5173",)),
        SessionStore(ttl_seconds=60, max_sessions=5),
    )

    with TestClient(app) as client:
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        simple = client.get(
            "/api/health",
            headers={"Origin": "http://localhost:5173"},
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert simple.headers["access-control-expose-headers"] == "Content-Disposition"


def test_unexpected_errors_use_the_same_envelope() -> None:
    app = create_app(ApiSettings(), SessionStore(ttl_seconds=60, max_sessions=5))

    @app.get("/api/boom")
    def boom() -> None:
        raise RuntimeError("internal detail that must not leak")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/boom")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "internal detail" not in response.text


def test_responses_are_normalised_for_the_wire() -> None:
    response = NormalisedJSONResponse(content={"ratio": 2.0 / 3.0, "when": date(2026, 1, 2)})

    assert json.loads(response.body) == {"ratio": 0.666667, "when": "2026-01-02"}


def test_a_session_without_a_dataset_cannot_be_described() -> None:
    session = Session(id="empty", created_at=0.0, last_accessed=0.0)

    with pytest.raises(ApiError) as caught:
        session_payload(session)

    assert caught.value.status_code == 409
    assert caught.value.code == "DATASET_NOT_LOADED"
