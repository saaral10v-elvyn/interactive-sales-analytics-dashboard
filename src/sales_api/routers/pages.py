"""Dashboard page payloads: one endpoint per screen.

Each endpoint returns the exact body recorded in ``tests/golden``. The request
body is optional; omitting it selects the state the dashboard opens with, while
sending one applies the same clamping rules as ``POST .../filters/resolve``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from sales_api.dependencies import SessionDep
from sales_api.filtering import default_request_state, resolve_request_state
from sales_api.schemas import ExplorerRequest, FilterRequest
from sales_api.views import require_cleaned_dataset
from sales_dashboard.models import CleanedDataset, FilterState
from sales_dashboard.page_payloads import (
    DEFAULT_EXPLORER_LIMIT,
    explorer_payload,
    overview_payload,
    products_payload,
    regions_payload,
)

router = APIRouter(prefix="/api/datasets", tags=["pages"])


def _resolved_state(cleaned: CleanedDataset, request: FilterRequest | None) -> FilterState:
    """Use the opening state when no selection was sent."""
    if request is None:
        return default_request_state(cleaned)
    return resolve_request_state(cleaned, request)


@router.post("/{session_id}/overview")
def get_overview(session: SessionDep, request: FilterRequest | None = None) -> dict[str, Any]:
    """Return the Overview page: KPIs, trend, breakdowns and insights."""
    cleaned = require_cleaned_dataset(session)
    return overview_payload(cleaned, _resolved_state(cleaned, request))


@router.post("/{session_id}/products")
def get_products(session: SessionDep, request: FilterRequest | None = None) -> dict[str, Any]:
    """Return the Products page: table, ranking, Pareto and drill-down."""
    cleaned = require_cleaned_dataset(session)
    return products_payload(cleaned, _resolved_state(cleaned, request))


@router.post("/{session_id}/regions")
def get_regions(session: SessionDep, request: FilterRequest | None = None) -> dict[str, Any]:
    """Return the Regions page: table, mix and multi-line trend."""
    cleaned = require_cleaned_dataset(session)
    return regions_payload(cleaned, _resolved_state(cleaned, request))


@router.post("/{session_id}/explorer")
def get_explorer(session: SessionDep, request: ExplorerRequest | None = None) -> dict[str, Any]:
    """Return the Data Explorer: counts, search results and preview slice."""
    cleaned = require_cleaned_dataset(session)
    state = _resolved_state(cleaned, request)
    if request is None:
        return explorer_payload(cleaned, state, limit=DEFAULT_EXPLORER_LIMIT)
    return explorer_payload(
        cleaned,
        state,
        search=request.search,
        limit=request.limit,
    )
