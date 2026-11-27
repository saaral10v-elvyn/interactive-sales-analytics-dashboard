"""CSV downloads for the cleaned data, the current selection and the report.

The domain serialisers produce the same bytes the golden fixtures record, so an
export is reproducible: same dataset, same filter selection, same search, same
size and SHA-256.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Response

from sales_api.dependencies import SessionDep
from sales_api.filtering import resolve_request_state
from sales_api.schemas import FilteredExportRequest
from sales_api.views import require_cleaned_dataset
from sales_dashboard.explorer import search_dataframe
from sales_dashboard.exports import (
    CSV_MIME,
    dataframe_to_csv_bytes,
    export_filename,
    quality_report_csv_bytes,
)
from sales_dashboard.filters import apply_filters
from sales_dashboard.models import CleanedDataset

router = APIRouter(prefix="/api/datasets", tags=["exports"])


def _now() -> datetime:
    """Indirection so tests can freeze the filename timestamp."""
    return datetime.now()


def _csv_response(data: bytes, cleaned: CleanedDataset, label: str) -> Response:
    """Wrap CSV bytes in a download with a safe, timestamped filename."""
    filename = export_filename(cleaned.source_filename, label, timestamp=_now())
    return Response(
        content=data,
        media_type=CSV_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{session_id}/exports/cleaned")
def download_cleaned(session: SessionDep) -> Response:
    """Download every cleaned row, with the UTF-8 BOM Excel expects."""
    cleaned = require_cleaned_dataset(session)
    return _csv_response(
        dataframe_to_csv_bytes(cleaned.dataframe),
        cleaned,
        "cleaned",
    )


@router.post("/{session_id}/exports/filtered")
def download_filtered(
    session: SessionDep,
    request: FilteredExportRequest | None = None,
) -> Response:
    """Download the filtered rows, optionally narrowed by the explorer search."""
    cleaned = require_cleaned_dataset(session)
    selection = request or FilteredExportRequest()
    state = resolve_request_state(cleaned, selection)
    filtered = search_dataframe(
        apply_filters(cleaned.dataframe, state),
        selection.search,
    )
    return _csv_response(
        dataframe_to_csv_bytes(filtered),
        cleaned,
        "filtered",
    )


@router.get("/{session_id}/exports/quality-report")
def download_quality_report(session: SessionDep) -> Response:
    """Download the data-quality report as a tidy CSV."""
    cleaned = require_cleaned_dataset(session)
    return _csv_response(
        quality_report_csv_bytes(
            cleaned.report,
            source_filename=cleaned.source_filename,
            revenue_source=cleaned.revenue_source,
            date_format_used=cleaned.date_format_used,
        ),
        cleaned,
        "quality_report",
    )
