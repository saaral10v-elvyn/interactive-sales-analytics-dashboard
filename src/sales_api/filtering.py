"""Filter resolution shared by the filter and page endpoints.

The filter endpoints and the page endpoints must interpret a request body in
exactly the same way. Keeping the rules here means a page can never disagree
with the filter panel that produced its state.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from sales_api.errors import ApiError
from sales_api.schemas import FilterRequest
from sales_dashboard.filters import (
    DEFAULT_DATE_PRESET,
    dataset_date_bounds,
    default_filter_state,
    preset_range,
    resolve_filter_state,
)
from sales_dashboard.models import CleanedDataset, FilterState


def require_date_bounds(dataframe: pd.DataFrame) -> tuple[date, date]:
    """Return the dataset date range or answer 409 when there is none."""
    bounds = dataset_date_bounds(dataframe)
    if bounds is None:
        raise ApiError(
            status_code=409,
            code="NO_DATE_COLUMN",
            message="The cleaned dataset has no usable order dates.",
        )
    return bounds


def default_request_state(cleaned: CleanedDataset) -> FilterState:
    """Return the state the dashboard opens with."""
    require_date_bounds(cleaned.dataframe)
    state = default_filter_state(cleaned.dataframe)
    assert state is not None
    return state


def resolve_request_state(cleaned: CleanedDataset, request: FilterRequest) -> FilterState:
    """Clamp a proposed selection to the dataset, mirroring the filter endpoint."""
    dataframe = cleaned.dataframe
    bounds = require_date_bounds(dataframe)

    if request.preset is not None and request.preset != "custom":
        start, end = preset_range(request.preset, bounds[0], bounds[1])
        preset = request.preset
    elif request.start_date is not None or request.end_date is not None:
        start = request.start_date or bounds[0]
        end = request.end_date or bounds[1]
        preset = "custom"
    else:
        start, end = preset_range(DEFAULT_DATE_PRESET, bounds[0], bounds[1])
        preset = DEFAULT_DATE_PRESET

    return resolve_filter_state(
        dataframe,
        FilterState(
            start_date=start,
            end_date=end,
            preset=preset,
            categories=tuple(request.categories),
            regions=tuple(request.regions),
            products=tuple(request.products),
            statuses=tuple(request.statuses),
        ),
    )
