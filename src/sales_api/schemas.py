"""Request models for the API.

Only requests are modelled here. Responses are dicts produced by
:mod:`sales_dashboard.payloads` so the HTTP layer and the golden fixtures keep
using one serialiser.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sales_dashboard.models import DateFormatDecision, DatePreset
from sales_dashboard.page_payloads import DEFAULT_EXPLORER_LIMIT, MAX_EXPLORER_LIMIT
from sales_dashboard.schema import FIELD_ORDER


class MappingRequest(BaseModel):
    """Manual column mapping: canonical field -> source column (null removes)."""

    model_config = ConfigDict(extra="forbid")

    fields: dict[str, str | None] = Field(default_factory=dict)

    @field_validator("fields")
    @classmethod
    def _known_fields(cls, value: dict[str, str | None]) -> dict[str, str | None]:
        unknown = sorted(set(value) - set(FIELD_ORDER))
        if unknown:
            raise ValueError(f"Unknown canonical fields: {', '.join(unknown)}")
        return value


class CleaningRequest(BaseModel):
    """Choices that affect the cleaning run."""

    model_config = ConfigDict(extra="forbid")

    date_format: DateFormatDecision = "auto"
    exclude_statuses: bool = True


class FilterRequest(BaseModel):
    """A filter selection to validate and clamp against the dataset."""

    model_config = ConfigDict(extra="forbid")

    start_date: date | None = None
    end_date: date | None = None
    preset: DatePreset | None = None
    categories: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)
    statuses: list[str] = Field(default_factory=list)


class ExplorerRequest(FilterRequest):
    """A filter selection plus the explorer's search and preview limit.

    ``search`` is omitted by default, which asks the server to pick a stable
    term from the data. Send ``""`` for no search.
    """

    search: str | None = None
    limit: int = Field(default=DEFAULT_EXPLORER_LIMIT, ge=1, le=MAX_EXPLORER_LIMIT)


class FilteredExportRequest(FilterRequest):
    """A filter selection plus the explorer search applied to the export.

    Unlike the explorer payload, the default is no search: an export should
    contain everything the filters selected unless a term is sent.
    """

    search: str = ""
