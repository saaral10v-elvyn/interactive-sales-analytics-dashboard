"""Contract tests for the Overview, Products, Regions and Explorer endpoints.

Each page body must equal the payload frozen in ``tests/golden/demo.json`` for
the default, narrow and zero-row selections, which keeps the React frontend on
the same contract as the v1.0.0 baseline.
"""

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
PAGES = ("overview", "products", "regions", "explorer")


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


def _golden() -> dict[str, Any]:
    return json.loads((GOLDEN_DIR / "demo.json").read_text(encoding="utf-8"))


def _page(client: TestClient, session_id: str, page: str, body: Any = None) -> Any:
    url = f"/api/datasets/{session_id}/{page}"
    if body is None:
        return client.post(url)
    return client.post(url, json=body)


def test_default_page_payloads_match_the_frozen_contract(
    client: TestClient,
    cleaned_demo: str,
) -> None:
    golden = _golden()["pages"]["default"]

    for page in PAGES:
        response = _page(client, cleaned_demo, page)
        assert response.status_code == 200, page
        assert response.json() == golden[page], page


def test_an_empty_body_selects_the_opening_state(
    client: TestClient,
    cleaned_demo: str,
) -> None:
    golden = _golden()["pages"]

    response = _page(client, cleaned_demo, "overview", {})
    assert response.status_code == 200
    assert response.json() == golden["default"]["overview"]
    assert response.json()["context"]["filters"] == golden["default_state"]


def test_a_narrow_selection_matches_the_frozen_pages(
    client: TestClient,
    cleaned_demo: str,
) -> None:
    golden = _golden()["pages"]
    state = golden["narrow_state"]

    for page in ("overview", "products"):
        response = _page(client, cleaned_demo, page, state)
        assert response.status_code == 200, page
        assert response.json() == golden["narrow"][page], page


def test_an_empty_selection_matches_the_frozen_pages(
    client: TestClient,
    cleaned_demo: str,
) -> None:
    golden = _golden()["pages"]
    state = golden["empty_state"]

    for page in PAGES:
        response = _page(client, cleaned_demo, page, state)
        assert response.status_code == 200, page
        assert response.json() == golden["empty"][page], page


def test_page_bodies_are_clamped_like_the_filter_endpoint(
    client: TestClient,
    cleaned_demo: str,
) -> None:
    response = _page(
        client,
        cleaned_demo,
        "overview",
        {"categories": ["No such category"], "start_date": "1900-01-01"},
    )

    assert response.status_code == 200
    context = response.json()["context"]
    assert context["filters"]["categories"] == []
    assert context["filters"]["start_date"] == _golden()["pages"]["bounds"][0]


def test_explorer_accepts_an_explicit_search_and_limit(
    client: TestClient,
    cleaned_demo: str,
) -> None:
    golden = _golden()["pages"]["default"]["explorer"]
    term = golden["search_term"]
    assert term

    response = _page(
        client,
        cleaned_demo,
        "explorer",
        {"search": term, "limit": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["search_term"] == term
    assert body["matching_rows"] == golden["matching_rows"]
    assert body["rows_shown"] == min(5, golden["matching_rows"])
    assert body["preview"] == golden["preview"][:5]


def test_explorer_search_is_case_insensitive_and_literal(
    client: TestClient,
    cleaned_demo: str,
) -> None:
    term = _golden()["pages"]["default"]["explorer"]["search_term"]

    lowered = _page(client, cleaned_demo, "explorer", {"search": term.lower()}).json()
    literal = _page(client, cleaned_demo, "explorer", {"search": "%"}).json()

    assert lowered["matching_rows"] == _golden()["pages"]["default"]["explorer"]["matching_rows"]
    assert literal["matching_rows"] < literal["filtered_rows"]
    assert literal["search_term"] == "%"


def test_explorer_without_a_search_returns_every_filtered_row(
    client: TestClient,
    cleaned_demo: str,
) -> None:
    body = _page(client, cleaned_demo, "explorer", {"search": ""}).json()

    assert body["search_term"] == ""
    assert body["matching_rows"] == body["filtered_rows"]
    assert body["rows_shown"] == min(25, body["filtered_rows"])


def test_explorer_limit_is_bounded(
    client: TestClient,
    cleaned_demo: str,
) -> None:
    for limit in (0, 501):
        response = _page(client, cleaned_demo, "explorer", {"limit": limit})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_page_payloads_before_cleaning_are_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/datasets",
        files={"file": ("sample.csv", NO_ORDER_ID_CSV.encode(), "text/csv")},
    )
    session_id = response.json()["session_id"]

    for page in PAGES:
        missing = _page(client, session_id, page)
        assert missing.status_code == 409, page
        assert missing.json()["error"]["code"] == "DATASET_NOT_CLEANED"


def test_page_payloads_without_dates_are_rejected(client: TestClient) -> None:
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

    for page in PAGES:
        missing = _page(client, session_id, page)
        assert missing.status_code == 409, page
        assert missing.json()["error"]["code"] == "NO_DATE_COLUMN"


def test_page_request_shape_is_validated(
    client: TestClient,
    cleaned_demo: str,
) -> None:
    extra = _page(client, cleaned_demo, "products", {"unexpected": True})
    assert extra.status_code == 422
    assert extra.json()["error"]["code"] == "INVALID_REQUEST"

    preset = _page(client, cleaned_demo, "regions", {"preset": "yesterday"})
    assert preset.status_code == 422
    assert preset.json()["error"]["code"] == "INVALID_REQUEST"
