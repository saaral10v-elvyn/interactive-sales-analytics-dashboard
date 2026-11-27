"""Response bodies shared by several routers."""

from __future__ import annotations

from typing import Any

from sales_api.errors import ApiError
from sales_api.sessions import Session
from sales_dashboard.models import CleanedDataset, LoadedDataset
from sales_dashboard.payloads import cleaning_summary, dataset_summary


def session_payload(session: Session) -> dict[str, Any]:
    """Describe a session's current dataset and cleaning state."""
    loaded = require_loaded_dataset(session)
    return {
        "session_id": session.id,
        "dataset": dataset_summary(loaded),
        "cleaned": cleaning_summary(session.cleaned) if session.cleaned is not None else None,
        "mapping_override": dict(session.mapping_override),
        "revision": session.revision,
    }


def require_loaded_dataset(session: Session) -> LoadedDataset:
    """Return the raw dataset or answer 409."""
    if session.loaded is None:
        raise ApiError(
            status_code=409,
            code="DATASET_NOT_LOADED",
            message="This session has no dataset yet.",
        )
    return session.loaded


def require_cleaned_dataset(session: Session) -> CleanedDataset:
    """Return the cleaned dataset or answer 409 until preparation is finished."""
    if session.cleaned is None:
        raise ApiError(
            status_code=409,
            code="DATASET_NOT_CLEANED",
            message="Clean the dataset before using the dashboard.",
        )
    return session.cleaned
