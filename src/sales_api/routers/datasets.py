"""Dataset session lifecycle: create from demo or upload, inspect, delete."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, File, Response, UploadFile

from sales_api.dependencies import SessionDep, StoreDep
from sales_api.errors import ApiError
from sales_api.sessions import SESSION_NOT_FOUND_MESSAGE, SessionStore
from sales_api.views import session_payload
from sales_dashboard.config import MAX_UPLOAD_BYTES, MAX_UPLOAD_MB
from sales_dashboard.loading import load_demo_dataset, read_csv_bytes
from sales_dashboard.models import LoadedDataset

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

CsvUpload = Annotated[UploadFile, File(description="Sales CSV file to analyse.")]


def _create(store: SessionStore, loaded: LoadedDataset) -> dict[str, Any]:
    session = store.create(loaded=loaded)
    return session_payload(session)


@router.post("/demo", status_code=201)
def create_demo_session(store: StoreDep) -> dict[str, Any]:
    """Load the bundled demo CSV into a new session."""
    return _create(store, load_demo_dataset())


@router.post("", status_code=201)
def upload_dataset(store: StoreDep, file: CsvUpload) -> dict[str, Any]:
    """Parse an uploaded CSV into a new session."""
    filename = (file.filename or "").strip()
    if not filename:
        raise ApiError(
            status_code=400,
            code="MISSING_FILENAME",
            message="The uploaded file has no filename.",
        )

    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise ApiError(
            status_code=400,
            code="EMPTY_UPLOAD",
            message="The uploaded file is empty.",
        )
    if len(data) > MAX_UPLOAD_BYTES:
        raise ApiError(
            status_code=413,
            code="UPLOAD_TOO_LARGE",
            message=f"Files must be {MAX_UPLOAD_MB} MB or smaller.",
            details={"max_upload_mb": MAX_UPLOAD_MB},
        )

    return _create(store, read_csv_bytes(data, filename, source="upload"))


@router.get("/{session_id}")
def get_dataset_session(session: SessionDep) -> dict[str, Any]:
    """Return the dataset summary and any completed cleaning result."""
    return session_payload(session)


@router.delete("/{session_id}", status_code=204)
def delete_dataset_session(session_id: str, store: StoreDep) -> Response:
    """Forget a session and the data it holds."""
    if not store.delete(session_id):
        raise ApiError(
            status_code=404,
            code="SESSION_NOT_FOUND",
            message=SESSION_NOT_FOUND_MESSAGE,
            details={"session_id": session_id},
        )
    return Response(status_code=204)
