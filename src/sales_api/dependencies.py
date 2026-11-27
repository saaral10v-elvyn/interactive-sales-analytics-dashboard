"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from sales_api.errors import ApiError
from sales_api.sessions import (
    SESSION_NOT_FOUND_MESSAGE,
    Session,
    SessionNotFoundError,
    SessionStore,
)


def get_store(request: Request) -> SessionStore:
    """Return the process-wide session store attached to the app."""
    return request.app.state.sessions


StoreDep = Annotated[SessionStore, Depends(get_store)]


def get_session(session_id: str, store: StoreDep) -> Session:
    """Load a live session or answer 404 with the standard error envelope."""
    try:
        return store.get(session_id)
    except SessionNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code="SESSION_NOT_FOUND",
            message=SESSION_NOT_FOUND_MESSAGE,
            details={"session_id": session_id},
        ) from exc


SessionDep = Annotated[Session, Depends(get_session)]
