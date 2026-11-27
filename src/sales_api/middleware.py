"""Small, framework-level response hardening shared by every route."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


def install_security_headers(app: FastAPI) -> None:
    """Attach conservative headers without constraining React or Recharts.

    A strict Content-Security-Policy is deliberately left out: Recharts draws
    inline SVG styles, so a useful policy needs more design work than a blanket
    header.
    """

    @app.middleware("http")
    async def add_security_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response
