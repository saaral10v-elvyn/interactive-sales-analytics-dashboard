"""JSON responses normalised by the same serialiser as the fixtures."""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

from sales_dashboard.payloads import jsonable


class NormalisedJSONResponse(JSONResponse):
    """Round floats and convert dates exactly like the golden fixtures.

    FastAPI has already encoded the payload by the time this runs, so the
    conversion here is cheap. Doing it on every response means a client never
    sees a raw NumPy scalar or an unrounded KPI.
    """

    def render(self, content: Any) -> bytes:
        return super().render(jsonable(content))
