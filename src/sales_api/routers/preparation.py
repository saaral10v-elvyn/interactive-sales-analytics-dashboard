"""Manual mapping, date inspection and cleaning endpoints."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from fastapi import APIRouter

from sales_api.dependencies import SessionDep
from sales_api.errors import ApiError
from sales_api.schemas import CleaningRequest, MappingRequest
from sales_api.views import require_loaded_dataset, session_payload
from sales_dashboard.cleaning import (
    CleaningError,
    CleaningOptions,
    clean_dataset,
    inspect_date_column,
)
from sales_dashboard.dates import DateDecisionRequired
from sales_dashboard.payloads import cleaning_summary, jsonable
from sales_dashboard.profiling import profile_dataset
from sales_dashboard.schema import MappingError, resolve_mapping

router = APIRouter(prefix="/api/datasets", tags=["preparation"])


@router.put("/{session_id}/mapping")
def update_mapping(session: SessionDep, request: MappingRequest) -> dict[str, Any]:
    """Apply manual overrides, refresh the profile and discard any cleaning."""
    loaded = require_loaded_dataset(session)
    columns = [str(column) for column in loaded.dataframe.columns]
    try:
        mapping = resolve_mapping(columns, request.fields)
    except MappingError as exc:
        raise ApiError(
            status_code=422,
            code="INVALID_MAPPING",
            message=str(exc),
        ) from exc

    session.loaded = replace(
        loaded,
        mapping=mapping,
        profile=profile_dataset(loaded.dataframe, mapping),
    )
    session.cleaned = None
    session.mapping_override = {
        field: source for field, source in request.fields.items() if source is not None
    }
    session.revision += 1
    return session_payload(session)


@router.get("/{session_id}/date-inspection")
def get_date_inspection(session: SessionDep) -> dict[str, Any]:
    """Describe the mapped date column before a format decision is made."""
    loaded = require_loaded_dataset(session)
    inspection = inspect_date_column(loaded.dataframe, loaded.mapping)
    return {
        "session_id": session.id,
        "inspection": jsonable(inspection),
    }


@router.post("/{session_id}/cleaning")
def run_cleaning(session: SessionDep, request: CleaningRequest) -> dict[str, Any]:
    """Clean the loaded dataset, replacing any previous cleaning result."""
    loaded = require_loaded_dataset(session)
    options = CleaningOptions(
        date_format=request.date_format,
        exclude_statuses=request.exclude_statuses,
    )
    try:
        cleaned = clean_dataset(
            loaded.dataframe,
            loaded.mapping,
            options,
            source_filename=loaded.filename,
        )
    except DateDecisionRequired as exc:
        raise ApiError(
            status_code=409,
            code="DATE_DECISION_REQUIRED",
            message=str(exc),
            details={"inspection": jsonable(exc.inspection)},
        ) from exc
    except CleaningError as exc:
        raise ApiError(
            status_code=422,
            code="CLEANING_FAILED",
            message=str(exc),
        ) from exc

    session.cleaned = cleaned
    session.revision += 1
    return {
        "session_id": session.id,
        "cleaned": cleaning_summary(cleaned),
        "date_format_used": cleaned.date_format_used,
        "revision": session.revision,
    }
