"""Pure filtering logic for the dashboard.

Nothing in this module depends on a web framework. The API turns request values
into a :class:`~sales_dashboard.models.FilterState`, while the functions here
apply that state consistently to every KPI, chart and table.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Literal

import pandas as pd

from sales_dashboard.models import DatePreset, FilterState

DATE_PRESET_LABELS: dict[DatePreset, str] = {
    "all_time": "All time",
    "last_7_days": "Last 7 days",
    "last_30_days": "Last 30 days",
    "last_90_days": "Last 90 days",
    "this_month": "This month",
    "this_year": "This year",
    "custom": "Custom",
}

PRESET_KEYS: tuple[DatePreset, ...] = tuple(DATE_PRESET_LABELS)
SELECTABLE_PRESETS: tuple[DatePreset, ...] = tuple(key for key in PRESET_KEYS if key != "custom")
DEFAULT_DATE_PRESET: DatePreset = "last_90_days"

FILTER_FIELDS: tuple[str, ...] = ("category", "region", "product", "status")
_EMPTY_LABELS = {
    "category": "All categories",
    "region": "All regions",
    "product": "All products",
    "status": "All statuses",
}
_PLURAL_LABELS = {
    "category": "categories",
    "region": "regions",
    "product": "products",
    "status": "statuses",
}


def _as_dates(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def dataset_date_bounds(dataframe: pd.DataFrame) -> tuple[date, date] | None:
    """Return the earliest and latest order dates in a cleaned dataframe."""
    if dataframe.empty or "order_date" not in dataframe.columns:
        return None
    dates = _as_dates(dataframe["order_date"]).dropna()
    if dates.empty:
        return None
    return dates.min().date(), dates.max().date()


def preset_range(
    preset: DatePreset,
    min_date: date,
    max_date: date,
) -> tuple[date, date]:
    """Return an inclusive date range anchored to the dataset's latest date.

    Presets deliberately ignore today's date: a dataset that ends in the past
    should still show a useful "last 30 days" window. Ranges are clamped to the
    dataset so a short dataset never produces a start date before the data.
    """
    if min_date > max_date:
        min_date, max_date = max_date, min_date

    if preset in ("all_time", "custom"):
        return min_date, max_date
    if preset == "last_7_days":
        start = max_date - timedelta(days=6)
    elif preset == "last_30_days":
        start = max_date - timedelta(days=29)
    elif preset == "last_90_days":
        start = max_date - timedelta(days=89)
    elif preset == "this_month":
        start = date(max_date.year, max_date.month, 1)
    elif preset == "this_year":
        start = date(max_date.year, 1, 1)
    else:
        raise ValueError(f"Unknown date preset: {preset!r}")

    return max(start, min_date), max_date


def detect_preset(
    start_date: date,
    end_date: date,
    min_date: date,
    max_date: date,
) -> DatePreset:
    """Return the preset matching a range, or ``custom`` when none match."""
    for preset in SELECTABLE_PRESETS:
        if preset_range(preset, min_date, max_date) == (start_date, end_date):
            return preset
    return "custom"


def previous_period(
    start_date: date,
    end_date: date,
) -> tuple[date, date]:
    """Return the equal-length period immediately before a date range."""
    length = max((end_date - start_date).days + 1, 1)
    previous_end = start_date - timedelta(days=1)
    previous_start = previous_end - timedelta(days=length - 1)
    return previous_start, previous_end


def _sorted_unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for value in values:
        shown = str(value)
        if shown and shown not in seen:
            seen[shown] = None
    return tuple(sorted(seen, key=str.casefold))


def filter_options(dataframe: pd.DataFrame) -> dict[str, tuple[str, ...]]:
    """Return sorted, non-empty values available for each filter dimension."""
    options: dict[str, tuple[str, ...]] = {}
    for field in FILTER_FIELDS:
        if field not in dataframe.columns:
            continue
        text = dataframe[field].astype("string").str.strip()
        usable = text[text.ne("") & text.notna()]
        options[field] = _sorted_unique(str(value) for value in usable.dropna().unique())
    return options


def _sanitize_selection(
    selected: tuple[str, ...],
    available: tuple[str, ...],
) -> tuple[str, ...]:
    allowed = set(available)
    return _sorted_unique(value for value in selected if value in allowed)


def resolve_filter_state(
    dataframe: pd.DataFrame,
    state: FilterState,
) -> FilterState:
    """Clamp dates and drop selections that no longer exist in the dataset."""
    bounds = dataset_date_bounds(dataframe)
    if bounds is None:
        return state

    min_date, max_date = bounds
    start = min(max(state.start_date, min_date), max_date)
    end = min(max(state.end_date, min_date), max_date)
    if start > end:
        start, end = end, start

    options = filter_options(dataframe)
    return FilterState(
        start_date=start,
        end_date=end,
        preset=detect_preset(start, end, min_date, max_date),
        categories=_sanitize_selection(state.categories, options.get("category", ())),
        regions=_sanitize_selection(state.regions, options.get("region", ())),
        products=_sanitize_selection(state.products, options.get("product", ())),
        statuses=_sanitize_selection(state.statuses, options.get("status", ())),
    )


def default_filter_state(dataframe: pd.DataFrame) -> FilterState | None:
    """Return the state the dashboard opens with, or None without usable dates."""
    bounds = dataset_date_bounds(dataframe)
    if bounds is None:
        return None
    start, end = preset_range(DEFAULT_DATE_PRESET, bounds[0], bounds[1])
    state = FilterState(
        start_date=start,
        end_date=end,
        preset=DEFAULT_DATE_PRESET,
    )
    return resolve_filter_state(dataframe, state)


def apply_filters(dataframe: pd.DataFrame, state: FilterState) -> pd.DataFrame:
    """Return the rows matching every active filter."""
    if dataframe.empty:
        return dataframe.copy()

    frame = dataframe
    if "order_date" in frame.columns:
        dates = _as_dates(frame["order_date"])
        in_range = dates.between(
            pd.Timestamp(state.start_date),
            pd.Timestamp(state.end_date),
            inclusive="both",
        )
        frame = frame.loc[in_range.fillna(False)]

    for field, selected in (
        ("category", state.categories),
        ("region", state.regions),
        ("product", state.products),
        ("status", state.statuses),
    ):
        if not selected or field not in frame.columns:
            continue
        values = frame[field].astype("string").str.strip()
        frame = frame.loc[values.isin(selected)]

    return frame.reset_index(drop=True)


def _describe_selection(
    values: tuple[str, ...],
    field: str,
) -> str:
    if not values:
        return _EMPTY_LABELS[field]
    if len(values) <= 2:
        return ", ".join(values)
    return f"{len(values)} {_PLURAL_LABELS[field]}"


def selected_filter_count(state: FilterState) -> int:
    """Return the number of active non-date filter values."""
    return len(state.categories) + len(state.regions) + len(state.products) + len(state.statuses)


def has_active_filters(
    state: FilterState,
    min_date: date,
    max_date: date,
) -> bool:
    """Return True when the state narrows the dataset in any way."""
    return bool(selected_filter_count(state)) or (
        state.start_date,
        state.end_date,
    ) != (min_date, max_date)


def summarize_filters(state: FilterState) -> str:
    """Build a compact human-readable summary of the active filters."""
    date_label = DATE_PRESET_LABELS.get(state.preset, "Custom")
    if state.preset == "all_time":
        date_text = "All dates"
    elif state.preset == "custom":
        date_text = f"Custom ({state.start_date:%d %b %Y} – {state.end_date:%d %b %Y})"
    else:
        date_text = f"{date_label} ({state.start_date:%d %b %Y} – {state.end_date:%d %b %Y})"

    parts = [
        date_text,
        _describe_selection(state.categories, "category"),
        _describe_selection(state.regions, "region"),
        _describe_selection(state.products, "product"),
    ]
    if state.statuses:
        parts.append(_describe_selection(state.statuses, "status"))
    return " · ".join(parts)


def filter_summary_lines(state: FilterState) -> Mapping[str, str]:
    """Return labelled filter values for compact UI display."""
    return {
        "Dates": f"{state.start_date:%d %b %Y} – {state.end_date:%d %b %Y}",
        "Categories": _describe_selection(state.categories, "category"),
        "Regions": _describe_selection(state.regions, "region"),
        "Products": _describe_selection(state.products, "product"),
        "Statuses": _describe_selection(state.statuses, "status"),
    }


def granularity_label(granularity: Literal["daily", "weekly", "monthly"]) -> str:
    """Return a friendly label for a trend granularity."""
    return {"daily": "Daily", "weekly": "Weekly", "monthly": "Monthly"}[granularity]
