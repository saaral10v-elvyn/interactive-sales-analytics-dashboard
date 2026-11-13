"""Data Explorer page: search, inspect and export the filtered dataset."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from sales_dashboard.explorer import search_dataframe
from sales_dashboard.exports import (
    CSV_MIME,
    dataframe_to_csv_bytes,
    export_filename,
    quality_report_csv_bytes,
)
from sales_dashboard.filters import apply_filters, summarize_filters
from sales_dashboard.formatting import format_date_range, format_inr, format_number
from sales_dashboard.state import get_cleaned
from sales_dashboard.ui.filters import render_dashboard_filters
from sales_dashboard.ui.layout import render_footer, render_metric_card, render_section

_ROW_LIMITS: tuple[str, ...] = ("25", "50", "100", "250", "500", "All")
_DEFAULT_LIMIT = "100"


def _render_missing_dataset() -> None:
    st.info(
        "The Data Explorer needs a cleaned dataset. Load a CSV on the Home page, "
        "then run **Validate and clean data** to unlock the dashboard."
    )
    render_footer()


def _filtered_revenue(dataframe: pd.DataFrame) -> float:
    if dataframe.empty or "revenue" not in dataframe.columns:
        return 0.0
    revenue = pd.to_numeric(dataframe["revenue"], errors="coerce")
    return float(revenue.sum())


def render() -> None:
    """Render the Data Explorer page."""
    cleaned = get_cleaned()
    if cleaned is None or cleaned.is_blocked or cleaned.dataframe.empty:
        _render_missing_dataset()
        return

    render_section(
        "Data Explorer",
        "Search the cleaned rows, choose which columns to preview, and download "
        "the filtered view, the full dataset or the quality report.",
    )

    filter_state = render_dashboard_filters(cleaned)
    filtered = apply_filters(cleaned.dataframe, filter_state)
    st.caption(
        f"Selected period: **{format_date_range(filter_state.start_date, filter_state.end_date)}** · "
        f"{format_number(len(filtered))} of {format_number(len(cleaned.dataframe))} cleaned rows · "
        f"{summarize_filters(filter_state)}"
    )

    if filtered.empty:
        st.warning(
            "No rows match the current filters. Widen the date range or clear one "
            "of the category, region, product or status filters."
        )

    all_columns = list(cleaned.dataframe.columns)
    search_column, limit_column = st.columns([2.4, 1])
    with search_column:
        query = st.text_input(
            "Search rows",
            placeholder="Search text or dates, for example a product, region or order ID",
            help="Case-insensitive search across text and date columns.",
        )
    with limit_column:
        limit_label = st.selectbox(
            "Rows to display",
            options=list(_ROW_LIMITS),
            index=_ROW_LIMITS.index(_DEFAULT_LIMIT),
            help="The table preview is capped to keep the page responsive. "
            "Downloads always include every matching row.",
        )

    selected_columns = st.multiselect(
        "Columns to preview",
        options=all_columns,
        default=all_columns,
        help="This only changes the table preview. Downloads include every cleaned column.",
    )

    searched = search_dataframe(filtered, query)
    limit = None if limit_label == "All" else int(limit_label)
    shown = searched.head(limit) if limit is not None else searched

    if not filtered.empty and searched.empty and query.strip():
        st.info(f"No rows match **{query.strip()}**. Clear the search box or try a different term.")

    counts = st.columns(4)
    with counts[0]:
        render_metric_card(
            "Filtered rows",
            format_number(len(filtered)),
            f"of {format_number(len(cleaned.dataframe))} cleaned rows",
        )
    with counts[1]:
        render_metric_card(
            "Matching rows",
            format_number(len(searched)),
            "After search" if query.strip() else "No search applied",
        )
    with counts[2]:
        render_metric_card(
            "Rows shown",
            format_number(len(shown)),
            f"Limit: {limit_label}",
        )
    with counts[3]:
        render_metric_card(
            "Filtered revenue",
            format_inr(_filtered_revenue(searched), compact=True),
            "Net revenue in the matching rows",
        )

    if not filtered.empty and not searched.empty:
        if not selected_columns:
            st.info("Choose at least one column to preview the cleaned data.")
        else:
            st.dataframe(
                shown.loc[:, selected_columns],
                hide_index=True,
                width="stretch",
            )
            st.caption(
                f"Showing {format_number(len(shown))} of {format_number(len(searched))} "
                "matching rows. Click a column header to sort. Downloads include every "
                "cleaned column and every matching row."
            )

    render_section(
        "Downloads",
        "Exports use the current global filters and search. Files are UTF-8 CSV "
        "with a byte-order mark so Excel opens Indian number formats correctly.",
    )

    stamp = datetime.now()
    download_columns = st.columns(3)
    with download_columns[0]:
        st.download_button(
            "Download filtered data (CSV)",
            data=dataframe_to_csv_bytes(searched),
            file_name=export_filename(
                cleaned.source_filename,
                "filtered",
                timestamp=stamp,
            ),
            mime=CSV_MIME,
            width="stretch",
            disabled=searched.empty,
            key="download_filtered_data",
        )
        st.caption(f"{format_number(len(searched))} matching rows")
    with download_columns[1]:
        st.download_button(
            "Download full cleaned data (CSV)",
            data=dataframe_to_csv_bytes(cleaned.dataframe),
            file_name=export_filename(
                cleaned.source_filename,
                "cleaned",
                timestamp=stamp,
            ),
            mime=CSV_MIME,
            width="stretch",
            key="download_cleaned_data",
        )
        st.caption(f"{format_number(len(cleaned.dataframe))} cleaned rows")
    with download_columns[2]:
        st.download_button(
            "Download quality report (CSV)",
            data=quality_report_csv_bytes(
                cleaned.report,
                source_filename=cleaned.source_filename,
                revenue_source=cleaned.revenue_source,
                date_format_used=cleaned.date_format_used,
            ),
            file_name=export_filename(
                cleaned.source_filename,
                "quality_report",
                timestamp=stamp,
            ),
            mime=CSV_MIME,
            width="stretch",
            key="download_quality_report",
        )
        st.caption(f"{format_number(len(cleaned.report.issues))} reported issues")

    render_footer()
