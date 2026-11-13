"""Dataset summary components used by the Home page."""

import pandas as pd
import streamlit as st

from sales_dashboard.formatting import (
    format_bytes,
    format_date,
    format_date_range,
    format_inr,
    format_number,
)
from sales_dashboard.models import LoadedDataset
from sales_dashboard.ui.layout import render_metric_card, render_section

_DELIMITER_NAMES = {
    ",": "Comma (,)",
    ";": "Semicolon (;)",
    "\t": "Tab",
    "|": "Pipe (|)",
}


def _optional_count(value: int | None, missing_note: str) -> tuple[str, str]:
    if value is None:
        return "—", missing_note
    return format_number(value), "Distinct values"


def render_dataset_summary(dataset: LoadedDataset) -> None:
    """Show dataset health, detected columns and a raw preview."""
    profile = dataset.profile

    render_section(
        "Dataset overview",
        "A quick check that the file was read correctly before analysis.",
    )

    first_row = st.columns(4)
    with first_row[0]:
        render_metric_card(
            "Rows",
            format_number(profile.row_count),
            f"{format_number(profile.column_count)} columns",
        )
    with first_row[1]:
        orders_value, orders_note = _optional_count(
            profile.order_count,
            "No order_id column",
        )
        render_metric_card("Orders", orders_value, orders_note)
    with first_row[2]:
        revenue_value = (
            format_inr(profile.net_revenue, compact=True)
            if profile.net_revenue is not None
            else "—"
        )
        revenue_note = (
            "Sum of line_total" if profile.net_revenue is not None else "line_total not provided"
        )
        render_metric_card("Net revenue", revenue_value, revenue_note)
    with first_row[3]:
        render_metric_card(
            "Date coverage",
            format_date_range(profile.date_min, profile.date_max, "%b %Y"),
            "Detected from order_date",
            small=True,
        )

    second_row = st.columns(4)
    with second_row[0]:
        products_value, products_note = _optional_count(
            profile.product_count,
            "product column not found",
        )
        render_metric_card("Products", products_value, products_note)
    with second_row[1]:
        categories_value, categories_note = _optional_count(
            profile.category_count,
            "category not provided",
        )
        render_metric_card("Categories", categories_value, categories_note)
    with second_row[2]:
        regions_value, regions_note = _optional_count(
            profile.region_count,
            "region not provided",
        )
        render_metric_card("Regions", regions_value, regions_note)
    with second_row[3]:
        render_metric_card(
            "Missing cells",
            format_number(profile.missing_cells),
            f"{format_number(profile.duplicate_rows)} duplicate rows",
        )

    for warning in dataset.warnings:
        st.warning(warning)

    if profile.missing_cells or profile.duplicate_rows:
        st.info(
            f"{format_number(profile.missing_cells)} empty cells and "
            f"{format_number(profile.duplicate_rows)} duplicate rows were found in "
            "the raw file. Run validation and cleaning below for the full report."
        )
    else:
        st.caption("Raw-file check: no empty cells or duplicate rows detected.")

    with st.expander("Dataset metadata and detected columns"):
        metadata = pd.DataFrame(
            [
                ("File", dataset.filename),
                ("Source", "Demo dataset" if dataset.source == "demo" else "Uploaded CSV"),
                ("File size", format_bytes(dataset.size_bytes)),
                ("Rows", format_number(profile.row_count)),
                ("Columns", format_number(profile.column_count)),
                ("Encoding", dataset.encoding),
                ("Delimiter", _DELIMITER_NAMES.get(dataset.delimiter, dataset.delimiter)),
                (
                    "Date coverage",
                    format_date_range(profile.date_min, profile.date_max)
                    if profile.date_min or profile.date_max
                    else "Not detected",
                ),
                (
                    "Net revenue",
                    format_inr(profile.net_revenue)
                    if profile.net_revenue is not None
                    else "Not available",
                ),
                ("Missing cells", format_number(profile.missing_cells)),
                ("Duplicate rows", format_number(profile.duplicate_rows)),
            ],
            columns=["Property", "Value"],
        )
        st.dataframe(metadata, hide_index=True, width="stretch")

    with st.expander("Preview raw data (first 25 rows)"):
        st.caption("Values are shown exactly as read from the file.")
        st.dataframe(
            dataset.dataframe.head(25),
            hide_index=True,
            width="stretch",
        )

    if profile.date_min or profile.date_max:
        st.caption(
            f"Loaded {format_date(profile.date_min)} to {format_date(profile.date_max)} · "
            f"{format_number(profile.row_count)} line items"
        )
