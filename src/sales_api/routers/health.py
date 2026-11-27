"""Health and metadata endpoints.

``/api/meta`` lets the frontend bootstrap labels, limits and the CSV guide
without duplicating any of the domain configuration in TypeScript.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from sales_api.dependencies import StoreDep
from sales_dashboard.config import (
    ALLOWED_EXTENSIONS,
    APP_NAME,
    APP_SHORT_NAME,
    APP_TAGLINE,
    APP_VERSION,
    CURRENCY_CODE,
    CURRENCY_SYMBOL,
    LARGE_DATASET_ROWS,
    MAX_ROWS,
    MAX_UPLOAD_MB,
    SUPPORTED_DELIMITERS,
    SUPPORTED_ENCODINGS,
)
from sales_dashboard.filters import (
    DATE_PRESET_LABELS,
    DEFAULT_DATE_PRESET,
    FILTER_FIELDS,
)
from sales_dashboard.schema import (
    FIELD_GUIDE,
    FIELD_LABELS,
    FIELD_ORDER,
    PRICE_FIELDS,
    REQUIRED_FIELDS,
)

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health(store: StoreDep) -> dict[str, Any]:
    """Report that the process is serving requests."""
    return {
        "status": "ok",
        "version": APP_VERSION,
        "active_sessions": len(store),
    }


@router.get("/meta")
def meta() -> dict[str, Any]:
    """Describe the application, its limits and its upload contract."""
    return {
        "app": {
            "name": APP_NAME,
            "short_name": APP_SHORT_NAME,
            "tagline": APP_TAGLINE,
            "version": APP_VERSION,
        },
        "currency": {"code": CURRENCY_CODE, "symbol": CURRENCY_SYMBOL},
        "limits": {
            "max_upload_mb": MAX_UPLOAD_MB,
            "max_rows": MAX_ROWS,
            "large_dataset_rows": LARGE_DATASET_ROWS,
        },
        "uploads": {
            "extensions": list(ALLOWED_EXTENSIONS),
            "encodings": list(SUPPORTED_ENCODINGS),
            "delimiters": list(SUPPORTED_DELIMITERS),
        },
        "fields": [
            {
                "column": guide.column,
                "requirement": guide.requirement,
                "description": guide.description,
                "example": guide.example,
            }
            for guide in FIELD_GUIDE
        ],
        "field_labels": dict(FIELD_LABELS),
        "field_order": list(FIELD_ORDER),
        "required_fields": list(REQUIRED_FIELDS),
        "price_fields": list(PRICE_FIELDS),
        "filters": {
            "fields": list(FILTER_FIELDS),
            "default_preset": DEFAULT_DATE_PRESET,
            "presets": [{"key": key, "label": label} for key, label in DATE_PRESET_LABELS.items()],
        },
    }
