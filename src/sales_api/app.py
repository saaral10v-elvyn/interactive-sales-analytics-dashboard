"""Application factory for the sales analytics API."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from sales_api.errors import install_error_handlers
from sales_api.middleware import install_security_headers
from sales_api.responses import NormalisedJSONResponse
from sales_api.routers import datasets, exports, filters, health, pages, preparation
from sales_api.sessions import SessionStore
from sales_api.settings import ApiSettings
from sales_api.static import mount_spa
from sales_dashboard.config import APP_NAME, APP_VERSION


def create_app(
    settings: ApiSettings | None = None,
    store: SessionStore | None = None,
) -> FastAPI:
    """Build the API, optionally with explicit settings and a session store.

    Passing a store makes tests and multi-instance deployments able to replace
    the default process-local one without touching the routers. When a static
    build directory is configured, the same process also serves the React SPA
    so the browser only ever talks to one origin.
    """
    settings = settings if settings is not None else ApiSettings.from_env()
    app = FastAPI(
        title=f"{APP_NAME} API",
        version=APP_VERSION,
        docs_url="/api/docs" if settings.enable_docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.enable_docs else None,
        default_response_class=NormalisedJSONResponse,
    )
    app.state.settings = settings
    app.state.sessions = (
        store
        if store is not None
        else SessionStore(
            ttl_seconds=settings.session_ttl_seconds,
            max_sessions=settings.max_sessions,
        )
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["*"],
            expose_headers=["Content-Disposition"],
        )

    if settings.gzip_min_size >= 0:
        app.add_middleware(GZipMiddleware, minimum_size=settings.gzip_min_size)

    if settings.security_headers:
        install_security_headers(app)

    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(datasets.router)
    app.include_router(preparation.router)
    app.include_router(filters.router)
    app.include_router(pages.router)
    app.include_router(exports.router)

    if settings.static_dir is not None:
        mount_spa(app, settings.static_dir)

    return app


app = create_app()
