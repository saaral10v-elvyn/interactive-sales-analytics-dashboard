"""Contract tests for mapping, date inspection and cleaning endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from parity_payloads import (
    AMBIGUOUS_DATES_CSV,
    CLASSIC_MODELS_CSV,
    MANUAL_OVERRIDES,
    MESSY_CSV,
    UNMAPPED_REQUIRED_CSV,
)

from sales_api.app import create_app
from sales_api.sessions import SessionStore
from sales_api.settings import ApiSettings

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = create_app(ApiSettings(), SessionStore(ttl_seconds=600, max_sessions=20))
    with TestClient(app) as test_client:
        yield test_client


def _golden(case: str) -> dict[str, Any]:
    return json.loads((GOLDEN_DIR / f"{case}.json").read_text(encoding="utf-8"))


def _upload(client: TestClient, csv_text: str, filename: str) -> dict[str, Any]:
    response = client.post(
        "/api/datasets",
        files={"file": (filename, csv_text.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _demo(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/datasets/demo")
    assert response.status_code == 201
    return response.json()


def _clean(
    client: TestClient,
    session_id: str,
    **options: Any,
) -> Any:
    body = {"date_format": "auto", "exclude_statuses": True, **options}
    return client.post(f"/api/datasets/{session_id}/cleaning", json=body)


def test_manual_override_matches_the_frozen_contract(client: TestClient) -> None:
    session = _upload(client, CLASSIC_MODELS_CSV, "classic.csv")
    response = client.put(
        f"/api/datasets/{session['session_id']}/mapping",
        json={"fields": MANUAL_OVERRIDES["classic_models"]},
    )

    assert response.status_code == 200
    body = response.json()
    golden = _golden("classic_models")
    assert body["dataset"]["mapping"] == golden["mapping_contract"]["manual_override"]["mapping"]
    assert body["mapping_override"] == MANUAL_OVERRIDES["classic_models"]
    assert body["cleaned"] is None
    assert body["revision"] == 1


def test_a_column_cannot_be_mapped_to_two_fields(client: TestClient) -> None:
    session = _upload(client, CLASSIC_MODELS_CSV, "classic.csv")
    response = client.put(
        f"/api/datasets/{session['session_id']}/mapping",
        json={"fields": {"order_id": "ORDERDATE"}},
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "INVALID_MAPPING"
    assert (
        error["message"]
        == _golden("classic_models")["mapping_contract"]["duplicate_source_error"]["message"]
    )


def test_an_unknown_source_column_is_rejected(client: TestClient) -> None:
    session = _upload(client, CLASSIC_MODELS_CSV, "classic.csv")
    response = client.put(
        f"/api/datasets/{session['session_id']}/mapping",
        json={"fields": {"order_id": "__not_a_column__"}},
    )

    assert response.status_code == 422
    assert (
        response.json()["error"]["message"]
        == _golden("classic_models")["mapping_contract"]["unknown_column_error"]["message"]
    )


def test_mapping_changes_discard_a_previous_cleaning(client: TestClient) -> None:
    session = _upload(client, CLASSIC_MODELS_CSV, "classic.csv")
    assert _clean(client, session["session_id"]).status_code == 200

    response = client.put(
        f"/api/datasets/{session['session_id']}/mapping",
        json={"fields": {"order_id": None}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["cleaned"] is None
    assert body["revision"] == 2
    assert client.get(f"/api/datasets/{session['session_id']}").json()["cleaned"] is None


def test_mapping_request_shape_is_validated(client: TestClient) -> None:
    session = _upload(client, CLASSIC_MODELS_CSV, "classic.csv")

    extra = client.put(
        f"/api/datasets/{session['session_id']}/mapping",
        json={"fields": {}, "unexpected": True},
    )
    assert extra.status_code == 422
    assert extra.json()["error"]["code"] == "INVALID_REQUEST"

    unknown = client.put(
        f"/api/datasets/{session['session_id']}/mapping",
        json={"fields": {"prodcut": "PRODUCTNAME"}},
    )
    assert unknown.status_code == 422
    assert unknown.json()["error"]["code"] == "INVALID_REQUEST"


def test_date_inspection_matches_the_frozen_contract(client: TestClient) -> None:
    demo = _demo(client)
    response = client.get(f"/api/datasets/{demo['session_id']}/date-inspection")
    assert response.status_code == 200
    assert response.json()["inspection"] == _golden("demo")["date_inspection"]

    ambiguous = _upload(client, AMBIGUOUS_DATES_CSV, "ambiguous.csv")
    response = client.get(f"/api/datasets/{ambiguous['session_id']}/date-inspection")
    assert response.json()["inspection"] == _golden("ambiguous_dates")["date_inspection"]


def test_cleaning_matches_the_frozen_contract(client: TestClient) -> None:
    demo = _demo(client)
    response = _clean(client, demo["session_id"])

    assert response.status_code == 200
    body = response.json()
    golden = _golden("demo")
    assert body["cleaned"] == golden["cleaning"]["auto"]["cleaned"]
    assert body["date_format_used"] == "auto"
    assert body["revision"] == 1

    stored = client.get(f"/api/datasets/{demo['session_id']}").json()
    assert stored["cleaned"] == golden["cleaning"]["auto"]["cleaned"]


def test_ambiguous_dates_require_and_then_accept_a_decision(client: TestClient) -> None:
    session = _upload(client, AMBIGUOUS_DATES_CSV, "ambiguous.csv")
    golden = _golden("ambiguous_dates")

    automatic = _clean(client, session["session_id"])
    assert automatic.status_code == 409
    error = automatic.json()["error"]
    assert error["code"] == "DATE_DECISION_REQUIRED"
    assert error["details"]["inspection"] == golden["cleaning"]["auto"]["error"]["inspection"]
    assert client.get(f"/api/datasets/{session['session_id']}").json()["cleaned"] is None

    decided = _clean(client, session["session_id"], date_format="DMY")
    assert decided.status_code == 200
    body = decided.json()
    assert body["date_format_used"] == "DMY"
    assert body["cleaned"] == golden["cleaning"]["dmy"]["cleaned"]


def test_incomplete_mapping_fails_closed(client: TestClient) -> None:
    session = _upload(client, UNMAPPED_REQUIRED_CSV, "unmapped.csv")
    response = _clean(client, session["session_id"])

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "CLEANING_FAILED"
    assert error["message"] == _golden("unmapped_required")["cleaning"]["auto"]["error"]["message"]


def test_excluding_statuses_is_an_explicit_choice(client: TestClient) -> None:
    session = _upload(client, MESSY_CSV, "messy.csv")

    excluded = _clean(client, session["session_id"], exclude_statuses=True)
    kept = _clean(client, session["session_id"], exclude_statuses=False)

    assert excluded.status_code == 200
    assert kept.status_code == 200
    assert kept.json()["cleaned"]["rows"] > excluded.json()["cleaned"]["rows"]


def test_cleaning_request_shape_is_validated(client: TestClient) -> None:
    session = _upload(client, MESSY_CSV, "messy.csv")
    response = client.post(
        f"/api/datasets/{session['session_id']}/cleaning",
        json={"date_format": "YMD"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
