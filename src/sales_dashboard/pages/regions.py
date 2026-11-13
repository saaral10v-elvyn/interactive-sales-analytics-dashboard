"""Regions page: regional performance, category mix and revenue trends."""

from __future__ import annotations

import streamlit as st

from sales_dashboard.analytics import (
    region_category_revenue,
    regional_performance,
    regional_revenue_trend,
)
from sales_dashboard.filters import apply_filters, summarize_filters
from sales_dashboard.formatting import format_date_range, format_number
from sales_dashboard.models import TrendGranularity
from sales_dashboard.state import get_cleaned
from sales_dashboard.ui.charts import (
    PLOTLY_CONFIG,
    build_region_category_figure,
    build_region_revenue_figure,
    build_regional_trend_figure,
)
from sales_dashboard.ui.filters import render_dashboard_filters
from sales_dashboard.ui.layout import render_footer, render_section
from sales_dashboard.ui.tables import render_region_performance_table

_GRANULARITY_OPTIONS: dict[str, TrendGranularity] = {
    "Daily": "daily",
    "Weekly": "weekly",
    "Monthly": "monthly",
}
_DEFAULT_GRANULARITY = "Monthly"


def _render_missing_dataset() -> None:
    st.info(
        "The Regions page needs a cleaned dataset. Load a CSV on the Home page, "
        "then run **Validate and clean data** to unlock the dashboard."
    )
    render_footer()


def _render_context(filter_state, *, filtered_rows: int, total_rows: int) -> None:
    st.caption(
        f"Selected period: **{format_date_range(filter_state.start_date, filter_state.end_date)}** · "
        f"{format_number(filtered_rows)} of {format_number(total_rows)} cleaned rows · "
        f"{summarize_filters(filter_state)}"
    )


def render() -> None:
    """Render the Regions analytics page."""
    cleaned = get_cleaned()
    if cleaned is None or cleaned.is_blocked or cleaned.dataframe.empty:
        _render_missing_dataset()
        return

    render_section(
        "Regions",
        "Regional revenue, category mix and trends for the current selection. "
        "Every table and chart uses the same globally filtered rows.",
    )

    filter_state = render_dashboard_filters(cleaned)
    filtered = apply_filters(cleaned.dataframe, filter_state)
    _render_context(
        filter_state,
        filtered_rows=len(filtered),
        total_rows=len(cleaned.dataframe),
    )

    if "region" not in cleaned.dataframe.columns:
        st.info(
            "This dataset has no `region` column, so regional analysis is unavailable. "
            "Add a region column to the source CSV or map one during preparation to "
            "unlock this page."
        )
        render_footer()
        return

    if filtered.empty:
        st.warning(
            "No rows match the current filters. Widen the date range or clear one "
            "of the category, region, product or status filters."
        )

    performance = regional_performance(
        filtered,
        order_id_available=cleaned.order_id_available,
    )

    render_section(
        "Regional performance",
        "Revenue, orders, units, average order value and revenue share by region.",
    )
    render_region_performance_table(performance)

    render_section(
        "Revenue by region",
        "Regions ranked by net revenue in the selected period.",
    )
    revenue_figure = build_region_revenue_figure(performance)
    if revenue_figure is None:
        st.info("No regional revenue matches the current filters.")
    else:
        st.plotly_chart(revenue_figure, width="stretch", config=PLOTLY_CONFIG)

    render_section(
        "Category mix by region",
        "Stacked category revenue for each region.",
    )
    if "category" not in cleaned.dataframe.columns:
        st.info(
            "This dataset has no `category` column, so the category-by-region mix is unavailable."
        )
    else:
        category_data = region_category_revenue(filtered)
        category_figure = build_region_category_figure(category_data)
        if category_figure is None:
            st.info("No category revenue matches the current filters.")
        else:
            st.plotly_chart(category_figure, width="stretch", config=PLOTLY_CONFIG)

    render_section(
        "Regional revenue trend",
        "Revenue over time for each region, with missing periods shown as zero.",
    )
    granularity_label = st.segmented_control(
        "Trend granularity",
        options=list(_GRANULARITY_OPTIONS),
        default=_DEFAULT_GRANULARITY,
        key="region_granularity",
        help="Change how regional revenue is grouped along the time axis.",
        persist_state="session",
    )
    label = granularity_label or _DEFAULT_GRANULARITY
    granularity = _GRANULARITY_OPTIONS[label]
    trend = regional_revenue_trend(filtered, granularity)
    trend_figure = build_regional_trend_figure(trend, granularity)
    if trend_figure is None:
        st.info("No dated regional revenue matches the current filters.")
    else:
        st.plotly_chart(trend_figure, width="stretch", config=PLOTLY_CONFIG)

    region_labels = filtered["region"].astype("string").str.strip()
    if (region_labels.eq("") | region_labels.isna()).any():
        st.caption("Rows with a blank region are grouped as **Unknown region**.")

    if not cleaned.order_id_available:
        st.caption(
            "This dataset has no usable `order_id` column, so each row is counted "
            "as one order in the regional metrics."
        )

    render_footer()
