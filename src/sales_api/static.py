"""Serve the built React single-page application from the API origin.

The SPA is a static bundle: one ``index.html``, hashed files under ``assets/``
and a few root-level files such as the favicon. Client routes are handled by
React Router, so an unknown extensionless path falls back to ``index.html``.

Two rules keep the API contract intact while doing that:

- ``/api`` and ``/exports`` are never served the SPA shell, even when the path
  does not match a registered route.
- A missing file below ``assets/`` returns 404 rather than HTML, so a broken
  bundle never masquerades as a successful page.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

ASSET_CACHE = "public, max-age=31536000, immutable"
PAGE_CACHE = "no-cache"
FILE_CACHE = "public, max-age=3600"
RESERVED_PATHS = {"api", "exports"}
RESERVED_PREFIXES = ("api/", "exports/")


class ImmutableStaticFiles(StaticFiles):
    """Static files with content-hashed names can be cached forever."""

    async def get_response(self, path: str, scope: Any) -> Any:
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = ASSET_CACHE
        return response


def mount_spa(app: FastAPI, directory: Path) -> bool:
    """Mount ``directory`` as the SPA, returning whether it was served.

    Nothing is mounted when the directory or its ``index.html`` is missing,
    which keeps API-only tests and deployments unchanged.
    """
    directory = directory.resolve()
    index = directory / "index.html"
    if not index.is_file():
        logger.warning("Static directory %s has no index.html; SPA serving is disabled", directory)
        return False

    assets = directory / "assets"
    if assets.is_dir():
        app.mount("/assets", ImmutableStaticFiles(directory=assets), name="assets")

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def serve_spa(full_path: str) -> FileResponse:
        if full_path in RESERVED_PATHS or full_path.startswith(RESERVED_PREFIXES):
            raise HTTPException(status_code=404)

        candidate = (directory / full_path).resolve() if full_path else directory
        if candidate != directory and directory not in candidate.parents:
            raise HTTPException(status_code=404)

        if full_path and candidate.is_file():
            return FileResponse(candidate, headers={"Cache-Control": FILE_CACHE})

        # A request for a missing file is a 404, not a client-side route.
        if Path(full_path).suffix:
            raise HTTPException(status_code=404)

        return FileResponse(index, headers={"Cache-Control": PAGE_CACHE})

    return True
