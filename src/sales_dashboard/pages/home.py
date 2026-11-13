"""Home page: upload or load a dataset and inspect its basic shape."""

import logging
from collections.abc import Callable

import pandas as pd
import streamlit as st

from sales_dashboard.config import (
    CURRENCY_CODE,
    DEMO_CSV_PATH,
    DEMO_END_DATE,
    DEMO_START_DATE,
    MAX_UPLOAD_MB,
)
from sales_dashboard.formatting import format_bytes, format_number
from sales_dashboard.loading import DataLoadError, load_demo_dataset, read_csv_bytes
from sales_dashboard.models import LoadedDataset
from sales_dashboard.schema import FIELD_GUIDE
from sales_dashboard.state import (
    clear_dataset,
    get_dataset,
    set_dataset,
    set_flash,
)
from sales_dashboard.ui.components import render_dataset_summary
from sales_dashboard.ui.layout import (
    render_flash,
    render_footer,
    render_hero,
    render_privacy_note,
    render_section,
)
from sales_dashboard.ui.preparation import render_preparation

logger = logging.getLogger(__name__)


def _load_with_flash(
    loader: Callable[[], LoadedDataset],
    success_message: Callable[[LoadedDataset], str],
) -> None:
    """Run a loader, store the result and show a one-shot message."""
    try:
        with st.spinner("Reading and profiling the dataset…"):
            dataset = loader()
    except DataLoadError as exc:
        set_flash(str(exc), "error")
    except Exception:
        logger.exception("Unexpected error while loading a dataset")
        set_flash(
            "Something went wrong while reading this file. "
            "Please check that it is a valid CSV and try again.",
            "error",
        )
    else:
        set_dataset(dataset)
        set_flash(success_message(dataset), "success")
    st.rerun()


def _sample_csv_bytes() -> bytes | None:
    try:
        return DEMO_CSV_PATH.read_bytes()
    except OSError:
        logger.exception("Could not read the sample CSV at %s", DEMO_CSV_PATH)
        return None


def _render_upload_card() -> None:
    with st.container(border=True):
        st.markdown(
            '<div class="sa-card-heading">Upload your sales data</div>',
            unsafe_allow_html=True,
        )
        st.caption(f"CSV only · up to {MAX_UPLOAD_MB} MB · processed in memory")
        uploaded = st.file_uploader(
            "Upload a sales CSV",
            type=["csv"],
            help=(
                "Required columns: order_date, product, quantity, and either "
                "unit_price or line_total."
            ),
        )

        if uploaded is not None:
            st.caption(f"Selected: {uploaded.name} · {format_bytes(uploaded.size)}")
        else:
            st.caption("Choose a file to enable the load button.")

        load_clicked = st.button(
            "Load uploaded CSV",
            type="primary" if uploaded is not None else "secondary",
            width="stretch",
            disabled=uploaded is None,
        )
        if load_clicked and uploaded is not None:
            _load_with_flash(
                lambda: read_csv_bytes(
                    uploaded.getvalue(),
                    uploaded.name,
                    source="upload",
                ),
                lambda dataset: (
                    f"{dataset.filename} loaded — "
                    f"{format_number(dataset.profile.row_count)} rows ready."
                ),
            )


def _render_demo_card() -> None:
    with st.container(border=True):
        st.markdown(
            '<div class="sa-card-heading">Explore the demo</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "18 months of realistic orders with multiple products, categories, "
            "regions, discounts and occasional returns."
        )

        if st.button(
            "Load demo dataset",
            type="primary",
            width="stretch",
        ):
            _load_with_flash(
                load_demo_dataset,
                lambda dataset: (
                    f"Demo dataset loaded — {format_number(dataset.profile.row_count)} rows ready."
                ),
            )

        sample_bytes = _sample_csv_bytes()
        if sample_bytes is not None:
            st.download_button(
                "Download sample CSV",
                data=sample_bytes,
                file_name="sales_demo.csv",
                mime="text/csv",
                width="stretch",
            )
        else:
            st.warning("The sample CSV is currently unavailable.")

        st.caption(
            f"{DEMO_START_DATE:%b %Y} – {DEMO_END_DATE:%b %Y} · "
            f"30 products · 5 regions · {CURRENCY_CODE}"
        )


def _render_schema_guide() -> None:
    render_section(
        "CSV format guide",
        "Your file needs the required columns below. Common aliases such as "
        "Date, Qty and Price are detected automatically.",
    )

    guide = pd.DataFrame(
        [
            {
                "Column": field.column,
                "Requirement": field.requirement,
                "Description": field.description,
                "Example": field.example,
            }
            for field in FIELD_GUIDE
        ]
    )
    st.dataframe(guide, hide_index=True, width="stretch")
    st.caption("* Provide at least one of unit_price or line_total.")

    with st.expander("Accepted aliases and data tips"):
        st.markdown(
            "**Common column aliases**\n\n"
            "- `order_date`: `date`, `purchase_date`, `invoice_date`, `created_at`\n"
            "- `product`: `product_name`, `item`, `item_name`, `description`\n"
            "- `quantity`: `qty`, `units`, `quantity_sold`\n"
            "- `unit_price`: `price`, `rate`, `price_per_unit`\n"
            "- `line_total`: `total`, `revenue`, `sales`, `amount`, `net_sales`\n"
            "- `region`: `territory`, `state`, `zone`, `area`, `location`\n\n"
            "**Data tips**\n\n"
            "- One row per line item is recommended; an `order_id` may repeat across "
            "several products.\n"
            "- Negative quantities are treated as returns.\n"
            "- Dates in `YYYY-MM-DD` format are recommended.\n"
            "- Amounts may include currency symbols and thousands separators."
        )


def render() -> None:
    """Render the Home page."""
    render_flash()
    render_hero()
    dataset = get_dataset()

    if dataset is not None:
        st.success(
            f"**{dataset.filename}** is loaded — "
            f"{format_number(dataset.profile.row_count)} rows and "
            f"{format_number(dataset.profile.column_count)} columns. "
            "Review the mapping, then validate and clean the data below."
        )

    upload_column, demo_column = st.columns([1.15, 0.85], gap="large")
    with upload_column:
        _render_upload_card()
    with demo_column:
        _render_demo_card()

    if dataset is not None:
        render_dataset_summary(dataset)
        render_preparation(dataset)
        if st.button("Clear loaded dataset", type="secondary"):
            clear_dataset()
            set_flash("Dataset cleared from this session.")
            st.rerun()

    _render_schema_guide()
    render_privacy_note()
    render_footer()
