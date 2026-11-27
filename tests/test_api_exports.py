"""Contract tests for the CSV download endpoints.

The exported bytes must be exactly the ones frozen in ``tests/golden/demo.json``
under ``exports``: same filename, same size and same SHA-256.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from parity_payloads import FIXED_TIMESTAMP, NO_ORDER_ID_CSV

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


@pytest.fixture
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> datetime:
    """Freeze export timestamps so filenames are predictable."""
    monkeypatch.setattr(
        "sales_api.routers.exports._now",
        lambda: FIXED_TIMESTAMP,
    )
    return FIXED_TIMESTAMP


def _golden() -> dict[str, Any]:
    return json.loads((GOLDEN_DIR / "demo.json").read_text(encoding="utf-8"))


def _disposition_filename(response: Any) -> str:
    header = response.headers["content-disposition"]
    assert header.startswith("attachment;")
    return header.split("filename=", 1)[1].strip('"')


def _assert_frozen(response: Any, export: dict[str, Any]) -> None:
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert _disposition_filename(response) == export["filename"]
    assert len(response.content) == export["size_bytes"]
    assert hashlib.sha256(response.content).hexdigest() == export["sha256"]
    assert response.content.startswith(b"\xef\xbb\xbf")


def _csv_rows(content: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))


def test_cleaned_export_matches_the_frozen_bytes(
    client: TestClient,
    cleaned_demo: str,
    frozen_clock: datetime,
) -> None:
    response = client.get(f"/api/datasets/{cleaned_demo}/exports/cleaned")

    _assert_frozen(response, _golden()["exports"]["cleaned"])
    assert len(_csv_rows(response.content)) == _golden()["cleaning"]["auto"]["cleaned"]["rows"] + 1


def test_quality_report_export_matches_the_frozen_bytes(
    client: TestClient,
    cleaned_demo: str,
    frozen_clock: datetime,
) -> None:
    response = client.get(f"/api/datasets/{cleaned_demo}/exports/quality-report")

    _assert_frozen(response, _golden()["exports"]["quality_report"])
    header, *rows = _csv_rows(response.content)
    assert header[0] == "Section"
    assert len(rows) == 10 + len(_golden()["cleaning"]["auto"]["cleaned"]["report"]["issues"])


def test_filtered_export_matches_the_frozen_bytes_for_the_opening_state(
    client: TestClient,
    cleaned_demo: str,
    frozen_clock: datetime,
) -> None:
    response = client.post(f"/api/datasets/{cleaned_demo}/exports/filtered")

    _assert_frozen(response, _golden()["exports"]["filtered"])
    rows = _csv_rows(response.content)
    assert len(rows) - 1 == _golden()["filters"]["filtered_rows"]


def test_filtered_export_applies_the_filter_selection(
    client: TestClient,
    cleaned_demo: str,
    frozen_clock: datetime,
) -> None:
    golden = _golden()
    response = client.post(
        f"/api/datasets/{cleaned_demo}/exports/filtered",
        json=golden["pages"]["narrow_state"],
    )

    assert response.status_code == 200
    rows = _csv_rows(response.content)
    assert len(rows) - 1 == golden["pages"]["narrow"]["overview"]["context"]["filtered_rows"]
    assert len(response.content) != golden["exports"]["filtered"]["size_bytes"]


def test_filtered_export_applies_the_search_term(
    client: TestClient,
    cleaned_demo: str,
    frozen_clock: datetime,
) -> None:
    golden = _golden()
    matching = golden["pages"]["default"]["explorer"]["matching_rows"]

    response = client.post(
        f"/api/datasets/{cleaned_demo}/exports/filtered",
        json={"search": golden["pages"]["default"]["explorer"]["search_term"]},
    )

    assert response.status_code == 200
    assert len(_csv_rows(response.content)) - 1 == matching
    assert matching < golden["filters"]["filtered_rows"]


def test_exports_before_cleaning_are_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/datasets",
        files={"file": ("sample.csv", NO_ORDER_ID_CSV.encode(), "text/csv")},
    )
    session_id = response.json()["session_id"]

    for method, path in (
        ("get", "/exports/cleaned"),
        ("post", "/exports/filtered"),
        ("get", "/exports/quality-report"),
    ):
        missing = getattr(client, method)(f"/api/datasets/{session_id}{path}")
        assert missing.status_code == 409, path
        assert missing.json()["error"]["code"] == "DATASET_NOT_CLEANED"


def test_raw_exports_work_without_dates_but_the_filtered_one_does_not(
    client: TestClient,
    frozen_clock: datetime,
) -> None:
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
    assert (
        client.post(
            f"/api/datasets/{session_id}/cleaning",
            json={"date_format": "auto"},
        ).status_code
        == 200
    )

    assert client.get(f"/api/datasets/{session_id}/exports/cleaned").status_code == 200
    assert client.get(f"/api/datasets/{session_id}/exports/quality-report").status_code == 200

    filtered = client.post(f"/api/datasets/{session_id}/exports/filtered")
    assert filtered.status_code == 409
    assert filtered.json()["error"]["code"] == "NO_DATE_COLUMN"


def test_filtered_export_request_shape_is_validated(
    client: TestClient,
    cleaned_demo: str,
) -> None:
    response = client.post(
        f"/api/datasets/{cleaned_demo}/exports/filtered",
        json={"unexpected": True},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_filenames_use_the_current_time_when_not_frozen(
    client: TestClient,
    cleaned_demo: str,
) -> None:
    response = client.get(f"/api/datasets/{cleaned_demo}/exports/cleaned")

    assert response.status_code == 200
    assert re.fullmatch(
        r"sales_demo_cleaned_\d{8}_\d{6}\.csv",
        _disposition_filename(response),
    )
