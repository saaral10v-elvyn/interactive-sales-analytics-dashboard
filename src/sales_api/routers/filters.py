"""Filter defaults and validation for the dashboard."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from sales_api.dependencies import SessionDep
from sales_api.filtering import (
    default_request_state,
    require_date_bounds,
    resolve_request_state,
)
from sales_api.schemas import FilterRequest
from sales_api.views import require_cleaned_dataset
from sales_dashboard.filters import (
    PRESET_KEYS,
    apply_filters,
    filter_options,
    preset_range,
    summarize_filters,
)
from sales_dashboard.payloads import filter_state_dict

router = APIRouter(prefix="/api/datasets", tags=["filters"])


@router.get("/{session_id}/filters")
def get_filters(session: SessionDep) -> dict[str, Any]:
    """Return the options, presets and state the dashboard opens with."""
    cleaned = require_cleaned_dataset(session)
    dataframe = cleaned.dataframe
    bounds = require_date_bounds(dataframe)
    state = default_request_state(cleaned)

    presets: dict[str, list[Any]] = {}
    for preset in PRESET_KEYS:
        if preset == "custom":
            continue
        start, end = preset_range(preset, bounds[0], bounds[1])
        presets[preset] = [start, end]

    return {
        "session_id": session.id,
        "bounds": [bounds[0], bounds[1]],
        "options": {field: list(values) for field, values in filter_options(dataframe).items()},
        "presets": presets,
        "state": filter_state_dict(state),
        "summary": summarize_filters(state),
        "filtered_rows": len(apply_filters(dataframe, state)),
        "total_rows": len(dataframe),
    }


@router.post("/{session_id}/filters/resolve")
def resolve_filters(session: SessionDep, request: FilterRequest) -> dict[str, Any]:
    """Clamp a proposed selection to the dataset and describe the result."""
    cleaned = require_cleaned_dataset(session)
    resolved = resolve_request_state(cleaned, request)
    dataframe = cleaned.dataframe

    return {
        "session_id": session.id,
        "state": filter_state_dict(resolved),
        "summary": summarize_filters(resolved),
        "filtered_rows": len(apply_filters(dataframe, resolved)),
        "total_rows": len(dataframe),
    }
