"""One error envelope for every failure the API can return.

The frontend only has to understand one shape::

    {"error": {"code": "SESSION_NOT_FOUND", "message": "...", "details": {...}}}

Domain exceptions are translated here so routers stay free of HTTP concerns.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from sales_dashboard.loading import DataLoadError

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """A deliberate API failure with a stable, machine-readable code."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def error_body(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the single error shape used by every handler."""
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return body


def install_error_handlers(app: FastAPI) -> None:
    """Register handlers that keep framework and domain errors consistent."""

    @app.exception_handler(ApiError)
    def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(DataLoadError)
    def handle_load_error(request: Request, exc: DataLoadError) -> JSONResponse:
        details = {"hint": exc.hint} if exc.hint else None
        return JSONResponse(
            status_code=400,
            content=error_body("INVALID_DATASET", exc.message, details),
        )

    @app.exception_handler(RequestValidationError)
    def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        # ``exc.errors()`` can carry non-serialisable context, so keep only the
        # three fields the frontend needs.
        errors = [
            {
                "location": list(error.get("loc", ())),
                "message": str(error.get("msg", "")),
                "type": str(error.get("type", "")),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_body(
                "INVALID_REQUEST",
                "The request is invalid.",
                {"errors": errors},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    def handle_http_error(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        known = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}
        code = known.get(exc.status_code, f"HTTP_{exc.status_code}")
        message = (
            exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, message),
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=error_body("INTERNAL_ERROR", "An unexpected error occurred."),
        )
