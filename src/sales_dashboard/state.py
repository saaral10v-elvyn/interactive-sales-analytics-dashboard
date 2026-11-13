"""Session-state helpers.

The raw dataset and the cleaned dataset are kept separately so the Home page
can always show what was read from the file, even after cleaning changes it.
"""

from dataclasses import replace

import streamlit as st

from sales_dashboard.models import CleanedDataset, ColumnMapping, LoadedDataset
from sales_dashboard.profiling import profile_dataset

_DATASET_KEY = "loaded_dataset"
_CLEANED_KEY = "cleaned_dataset"
_FLASH_KEY = "flash_message"
DASHBOARD_BOUNDS_KEY = "dashboard_date_bounds"

# Widget keys owned by the shared dashboard filter panel. They are cleared when
# the loaded dataset changes so a new file never inherits stale selections.
DASHBOARD_FILTER_KEYS: tuple[str, ...] = (
    "dash_preset",
    "dash_start",
    "dash_end",
    "dash_categories",
    "dash_regions",
    "dash_products",
    "dash_statuses",
    "product_drilldown",
    "product_granularity",
    "region_granularity",
    "dash_filter_store",
)


def init_state() -> None:
    """Create the keys used by the app without overwriting existing values."""
    st.session_state.setdefault(_DATASET_KEY, None)
    st.session_state.setdefault(_CLEANED_KEY, None)
    st.session_state.setdefault(_FLASH_KEY, None)


def reset_dashboard_filters() -> None:
    """Forget dashboard filter widgets and chart settings.

    This is safe to call before the dashboard widgets are created, such as when
    a new dataset is loaded on the Home page.
    """
    for key in DASHBOARD_FILTER_KEYS:
        st.session_state.pop(key, None)
    st.session_state.pop(DASHBOARD_BOUNDS_KEY, None)
    st.session_state.pop("overview_granularity", None)


def get_dataset() -> LoadedDataset | None:
    """Return the dataset currently loaded in this browser session."""
    return st.session_state.get(_DATASET_KEY)


def set_dataset(dataset: LoadedDataset) -> None:
    """Store a newly loaded dataset and discard previous derived state."""
    previous = st.session_state.get(_DATASET_KEY)
    if previous is not dataset:
        reset_dashboard_filters()
    st.session_state[_DATASET_KEY] = dataset
    clear_cleaned()


def clear_dataset() -> None:
    """Remove the current dataset and cleaning result from the session."""
    st.session_state[_DATASET_KEY] = None
    clear_cleaned()
    reset_dashboard_filters()


def update_dataset_mapping(dataset: LoadedDataset, mapping: ColumnMapping) -> LoadedDataset:
    """Apply a reviewed mapping and refresh the lightweight profile."""
    updated = replace(
        dataset,
        mapping=mapping,
        profile=profile_dataset(dataset.dataframe, mapping),
    )
    set_dataset(updated)
    return updated


def get_cleaned() -> CleanedDataset | None:
    """Return the cleaned dataset for this session, if cleaning has run."""
    return st.session_state.get(_CLEANED_KEY)


def set_cleaned(cleaned: CleanedDataset) -> None:
    """Store a completed cleaning result."""
    st.session_state[_CLEANED_KEY] = cleaned


def clear_cleaned() -> None:
    """Discard the current cleaning result."""
    st.session_state[_CLEANED_KEY] = None


def set_flash(message: str, kind: str = "success") -> None:
    """Queue a one-shot message to show after the next rerun."""
    st.session_state[_FLASH_KEY] = {"message": message, "kind": kind}


def pop_flash() -> dict[str, str] | None:
    """Return and clear the queued message."""
    flash = st.session_state.get(_FLASH_KEY)
    st.session_state[_FLASH_KEY] = None
    return flash
