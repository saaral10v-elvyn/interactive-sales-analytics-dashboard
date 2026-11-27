"""Contract tests for filter defaults and resolution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from parity_payloads import NO_ORDER_ID_CSV

from sales_api.app import create_app
from sales_api.sessions import SessionStore
from sales_api.settings import ApiSettings

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = create_app(ApiSettings(), SessionStore(ttl_seconds=600, max_sessions=20))
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def cleaned_demo(client: TestClient) -> str:
    session_id = client.post("/api/datasets/demo").json()["session_id"]
    response = client.post(
        f"/api/datasets/{session_id}/cleaning",
        json={"date_format": "auto"},
    )
    assert response.status_code == 200
    return session_id


def _golden(case: str = "demo") -> dict[str, Any]:
    return json.loads((GOLDEN_DIR / f"{case}.json").read_text(encoding="utf-8"))


def _resolve(client: TestClient, session_id: str, body: dict[str, Any]) -> Any:
    return client.post(f"/api/datasets/{session_id}/filters/resolve", json=body)


def test_default_filters_match_the_frozen_contract(
    client: TestClient,
    cleaned_demo: str,
) -> None:
    response = client.get(f"/api/datasets/{cleaned_demo}/filters")

    assert response.status_code == 200
    body = response.json()
    golden = _golden()

    assert body["bounds"] == golden["pages"]["bounds"]
    assert body["options"] == golden["pages"]["options"]
    assert body["presets"] == golden["pages"]["presets"]
    assert body["state"] == golden["pages"]["default_state"]
    assert body["state"] == golden["filters"]["default_state"]
    assert body["summary"] == golden["filters"]["summary"]
    assert body["filtered_rows"] == golden["filters"]["filtered_rows"]
    assert body["total_rows"] == golden["cleaning"]["auto"]["cleaned"]["rows"]


def test_a_narrow_selection_matches_the_frozen_page_context(
    client: TestClient,
    cleaned_demo: str,
) -> None:
    golden = _golden()
    state = golden["pages"]["narrow_state"]

    body = _resolve(client, cleaned_demo, state).json()

    assert body["state"] == state
    assert body["summary"] == golden["pages"]["narrow"]["overview"]["context"]["summary"]
    assert (
        body["filtered_rows"] == golden["pages"]["narrow"]["overview"]["context"]["filtered_rows"]
    )


def test_an_empty_selection_matches_the_frozen_zero_rows_context(
    client: TestClient,
    cleaned_demo: str,
) -> None:
    golden = _golden()
    state = golden["pages"]["empty_state"]

    body = _resolve(client, cleaned_demo, state).json()

    assert body["state"] == state
    assert body["filtered_rows"] == 0
    assert body["summary"] == golden["pages"]["empty"]["overview"]["context"]["summary"]


def test_unknown_values_are_removed_instead_of_rejected(
    client: TestClient,
    cleaned_demo: str,
) -> None:
    body = _resolve(
        client,
        cleaned_demo,
        {"categories": ["No such category"], "regions": ["Nowhere"]},
    ).json()

    assert body["state"]["categories"] == []
    assert body["state"]["regions"] == []
    assert body["filtered_rows"] > 0


def test_dates_are_clamped_to_the_dataset(
    client: TestClient,
    cleaned_demo: str,
) -> None:
    bounds = _golden()["pages"]["bounds"]

    body = _resolve(
        client,
        cleaned_demo,
        {"start_date": "1900-01-01", "end_date": "1900-01-02"},
    ).json()

    assert body["state"]["start_date"] == bounds[0]
    assert body["state"]["end_date"] == bounds[0]


def test_a_named_preset_takes_precedence_over_dates(
    client: TestClient,
    cleaned_demo: str,
) -> None:
    presets = _golden()["pages"]["presets"]

    body = _resolve(
        client,
        cleaned_demo,
        {
            "preset": "last_7_days",
            "start_date": "2025-05-01",
            "end_date": "2026-10-31",
        },
    ).json()

    assert body["state"]["preset"] == "last_7_days"
    assert body["state"]["start_date"] == presets["last_7_days"][0]
    assert body["state"]["end_date"] == presets["last_7_days"][1]


def test_filters_before_cleaning_are_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/datasets",
        files={"file": ("sample.csv", NO_ORDER_ID_CSV.encode(), "text/csv")},
    )
    session_id = response.json()["session_id"]

    missing = client.get(f"/api/datasets/{session_id}/filters")
    assert missing.status_code == 409
    assert missing.json()["error"]["code"] == "DATASET_NOT_CLEANED"

    resolved = _resolve(client, session_id, {"preset": "all_time"})
    assert resolved.status_code == 409
    assert resolved.json()["error"]["code"] == "DATASET_NOT_CLEANED"


def test_a_cleaned_dataset_without_dates_cannot_build_filters(client: TestClient) -> None:
    response = client.post(
        "/api/datasets",
        files={
            "file": (
                "undated.csv",
                b"order_id,order_date,product,quantity,unit_price\nX-1,not-a-date,Alpha,1,10\n",
                "text/csv",
            )
        },
    )
    session_id = response.json()["session_id"]

    cleaned = client.post(f"/api/datasets/{session_id}/cleaning", json={"date_format": "auto"})
    assert cleaned.status_code == 200
    assert cleaned.json()["cleaned"]["rows"] == 0
    assert cleaned.json()["cleaned"]["report"]["blocked"] is True

    missing = client.get(f"/api/datasets/{session_id}/filters")
    assert missing.status_code == 409
    assert missing.json()["error"]["code"] == "NO_DATE_COLUMN"

    resolved = _resolve(client, session_id, {"preset": "all_time"})
    assert resolved.status_code == 409
    assert resolved.json()["error"]["code"] == "NO_DATE_COLUMN"


def test_an_unknown_preset_is_a_validation_error(
    client: TestClient,
    cleaned_demo: str,
) -> None:
    response = _resolve(client, cleaned_demo, {"preset": "yesterday"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
