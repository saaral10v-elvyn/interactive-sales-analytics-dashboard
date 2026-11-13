"""Sidebar controls for the shared dashboard filters."""

from __future__ import annotations

from datetime import date

import streamlit as st

from sales_dashboard.filters import (
    DATE_PRESET_LABELS,
    DEFAULT_DATE_PRESET,
    PRESET_KEYS,
    SELECTABLE_PRESETS,
    apply_filters,
    dataset_date_bounds,
    detect_preset,
    filter_options,
    preset_range,
    summarize_filters,
)
from sales_dashboard.formatting import format_number
from sales_dashboard.models import CleanedDataset, FilterState
from sales_dashboard.state import DASHBOARD_BOUNDS_KEY

_MULTI_KEYS = {
    "category": "dash_categories",
    "region": "dash_regions",
    "product": "dash_products",
    "status": "dash_statuses",
}
_MULTI_STORE_KEYS = {
    "category": "categories",
    "region": "regions",
    "product": "products",
    "status": "statuses",
}
_FILTER_LABELS = {
    "category": "Category",
    "region": "Region",
    "product": "Product",
    "status": "Status",
}
_EMPTY_LABELS = {
    "category": "All categories",
    "region": "All regions",
    "product": "All products",
    "status": "All statuses",
}

# A plain session-state dictionary that mirrors the filter widgets. Streamlit
# can reset widget values for one run when a widget's page is first shown, so
# the widgets are not a reliable source of truth during a page switch. Reading
# this store keeps tables and charts filtered consistently on every page.
FILTER_STORE_KEY = "dash_filter_store"


def _store() -> dict[str, object]:
    store = st.session_state.get(FILTER_STORE_KEY)
    if not isinstance(store, dict):
        store = {}
        st.session_state[FILTER_STORE_KEY] = store
    return store


def _default_store(min_date: date, max_date: date) -> dict[str, object]:
    start, end = preset_range(DEFAULT_DATE_PRESET, min_date, max_date)
    return {
        "preset": detect_preset(start, end, min_date, max_date),
        "start": start,
        "end": end,
        **{key: [] for key in _MULTI_STORE_KEYS.values()},
    }


def _ensure_defaults(min_date: date, max_date: date) -> None:
    store = _store()
    defaults = _default_store(min_date, max_date)
    for key, value in defaults.items():
        store.setdefault(key, value)

    # A previous file may have had a wider range than the current dataset.
    if not isinstance(store["start"], date):
        store["start"] = min_date
    if not isinstance(store["end"], date):
        store["end"] = max_date
    store["start"] = min(store["start"], max_date)
    store["start"] = max(store["start"], min_date)
    store["end"] = min(store["end"], max_date)
    store["end"] = max(store["end"], min_date)
    if store["start"] > store["end"]:
        store["start"], store["end"] = store["end"], store["start"]


def _sanitize_store(options: dict[str, tuple[str, ...]]) -> None:
    store = _store()
    for field, store_key in _MULTI_STORE_KEYS.items():
        current = store.get(store_key, [])
        if not isinstance(current, list):
            current = []
        allowed = options.get(field, ())
        store[store_key] = [value for value in current if value in allowed]


def _sync_store() -> None:
    """Copy the current widget values into the authoritative store."""
    store = _store()
    store["preset"] = st.session_state.get("dash_preset", "custom")
    store["start"] = st.session_state.get("dash_start")
    store["end"] = st.session_state.get("dash_end")
    for field, widget_key in _MULTI_KEYS.items():
        value = st.session_state.get(widget_key, [])
        store[_MULTI_STORE_KEYS[field]] = list(value) if isinstance(value, list) else []


def _restore_widgets() -> None:
    """Seed the widgets from the store before they are created."""
    store = _store()
    st.session_state["dash_preset"] = store["preset"]
    st.session_state["dash_start"] = store["start"]
    st.session_state["dash_end"] = store["end"]
    for field, widget_key in _MULTI_KEYS.items():
        st.session_state[widget_key] = list(store[_MULTI_STORE_KEYS[field]])


def _apply_preset() -> None:
    preset = st.session_state.get("dash_preset", DEFAULT_DATE_PRESET)
    if preset not in SELECTABLE_PRESETS:
        _sync_store()
        return
    bounds = st.session_state.get(DASHBOARD_BOUNDS_KEY)
    if not bounds:
        _sync_store()
        return
    start, end = preset_range(preset, bounds[0], bounds[1])
    st.session_state["dash_start"] = start
    st.session_state["dash_end"] = end
    _sync_store()


def _on_start_change() -> None:
    st.session_state["dash_preset"] = "custom"
    start = st.session_state.get("dash_start")
    end = st.session_state.get("dash_end")
    if start is not None and end is not None and start > end:
        st.session_state["dash_end"] = start
    _sync_store()


def _on_end_change() -> None:
    st.session_state["dash_preset"] = "custom"
    start = st.session_state.get("dash_start")
    end = st.session_state.get("dash_end")
    if start is not None and end is not None and end < start:
        st.session_state["dash_start"] = end
    _sync_store()


def _reset_filters() -> None:
    bounds = st.session_state.get(DASHBOARD_BOUNDS_KEY)
    if bounds:
        defaults = _default_store(bounds[0], bounds[1])
    else:
        today = date.today()
        defaults = _default_store(today, today)
    st.session_state[FILTER_STORE_KEY] = defaults
    _restore_widgets()


def _build_state() -> FilterState:
    """Build the filter state from the authoritative store."""
    store = _store()
    return FilterState(
        start_date=store["start"],
        end_date=store["end"],
        preset=store["preset"],
        categories=tuple(store["categories"]),
        regions=tuple(store["regions"]),
        products=tuple(store["products"]),
        statuses=tuple(store["statuses"]),
    )


def render_dashboard_filters(cleaned: CleanedDataset) -> FilterState:
    """Render the shared dashboard filters in the sidebar and return their state."""
    bounds = dataset_date_bounds(cleaned.dataframe)
    if bounds is None:
        with st.sidebar:
            st.warning("This dataset has no usable order dates to filter.")
        today = date.today()
        return FilterState(start_date=today, end_date=today, preset="custom")

    min_date, max_date = bounds
    st.session_state[DASHBOARD_BOUNDS_KEY] = bounds
    _ensure_defaults(min_date, max_date)
    options = filter_options(cleaned.dataframe)
    _sanitize_store(options)
    _restore_widgets()

    with st.sidebar:
        st.divider()
        st.markdown("**Dashboard filters**")
        st.caption(
            f"{cleaned.source_filename} · {format_number(len(cleaned.dataframe))} cleaned rows"
        )

        st.selectbox(
            "Date preset",
            # "Custom" is included so manual date edits keep a truthful label
            # instead of falling back to the first preset.
            options=list(PRESET_KEYS),
            format_func=lambda option: DATE_PRESET_LABELS[option],
            key="dash_preset",
            on_change=_apply_preset,
            persist_state="session",
        )
        from_column, to_column = st.columns(2)
        with from_column:
            st.date_input(
                "From",
                key="dash_start",
                min_value=min_date,
                max_value=max_date,
                format="DD/MM/YYYY",
                on_change=_on_start_change,
                persist_state="session",
            )
        with to_column:
            st.date_input(
                "To",
                key="dash_end",
                min_value=min_date,
                max_value=max_date,
                format="DD/MM/YYYY",
                on_change=_on_end_change,
                persist_state="session",
            )

        for field in ("category", "region", "product", "status"):
            field_options = options.get(field, ())
            if not field_options:
                continue
            st.multiselect(
                _FILTER_LABELS[field],
                options=list(field_options),
                key=_MULTI_KEYS[field],
                placeholder=_EMPTY_LABELS[field],
                on_change=_sync_store,
                persist_state="session",
            )

        st.button(
            "Reset all filters",
            on_click=_reset_filters,
            width="stretch",
        )

        state = _build_state()
        filtered_count = len(apply_filters(cleaned.dataframe, state))
        st.caption(
            f"Showing {format_number(filtered_count)} of "
            f"{format_number(len(cleaned.dataframe))} rows"
        )
        st.caption(summarize_filters(state))

    return state
