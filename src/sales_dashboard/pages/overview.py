"""Overview page: KPIs, interactive charts and deterministic insights."""

from __future__ import annotations

from datetime import date

import streamlit as st

from sales_dashboard.analytics import (
    category_revenue,
    compute_dashboard_metrics,
    generate_insights,
    revenue_trend,
    top_products,
)
from sales_dashboard.filters import apply_filters
from sales_dashboard.formatting import format_date_range, format_number
from sales_dashboard.models import TrendGranularity
from sales_dashboard.state import get_cleaned
from sales_dashboard.ui.charts import (
    PLOTLY_CONFIG,
    build_category_figure,
    build_revenue_trend_figure,
    build_top_products_figure,
)
from sales_dashboard.ui.dashboard import render_insight_cards, render_kpi_cards
from sales_dashboard.ui.filters import render_dashboard_filters
from sales_dashboard.ui.layout import render_footer, render_section

_GRANULARITY_OPTIONS: dict[str, TrendGranularity] = {
    "Daily": "daily",
    "Weekly": "weekly",
    "Monthly": "monthly",
}
_DEFAULT_GRANULARITY = "Monthly"


def _render_missing_dataset() -> None:
    st.info(
        "The Overview needs a cleaned dataset. Load a CSV on the Home page, then "
        "run **Validate and clean data** to unlock the dashboard."
    )
    render_footer()


def _render_period_context(
    current_period: tuple[date, date],
    previous_period: tuple[date, date],
    *,
    filtered_rows: int,
    total_rows: int,
    previous_rows: int,
) -> None:
    st.caption(
        f"Selected period: **{format_date_range(*current_period)}** · "
        f"{format_number(filtered_rows)} of {format_number(total_rows)} cleaned rows. "
        f"Comparisons use the preceding equal-length period "
        f"({format_date_range(*previous_period)}"
        + (f", {format_number(previous_rows)} rows)." if previous_rows else ", no data).")
    )


def _render_trend(filtered, *, order_id_available: bool) -> None:
    granularity_label = st.segmented_control(
        "Trend granularity",
        options=list(_GRANULARITY_OPTIONS),
        default=_DEFAULT_GRANULARITY,
        key="overview_granularity",
        help="Change how revenue is grouped along the time axis.",
        persist_state="session",
    )
    label = granularity_label or _DEFAULT_GRANULARITY
    granularity = _GRANULARITY_OPTIONS[label]

    trend = revenue_trend(
        filtered,
        granularity,
        order_id_available=order_id_available,
    )
    figure = build_revenue_trend_figure(trend, granularity)
    if figure is None:
        st.info("No dated rows match the current filters, so there is no revenue trend to plot.")
        return
    st.plotly_chart(figure, width="stretch", config=PLOTLY_CONFIG)


def _render_breakdowns(filtered) -> None:
    left, right = st.columns(2, gap="large")

    with left:
        category_data = category_revenue(filtered)
        category_figure = build_category_figure(category_data)
        if category_figure is None:
            st.info("This dataset has no category column, so category revenue is unavailable.")
        else:
            st.plotly_chart(category_figure, width="stretch", config=PLOTLY_CONFIG)

    with right:
        product_data = top_products(filtered, limit=10)
        product_figure = build_top_products_figure(product_data)
        if product_figure is None:
            st.info("No products match the current filters.")
        else:
            st.plotly_chart(product_figure, width="stretch", config=PLOTLY_CONFIG)


def render() -> None:
    """Render the dashboard Overview."""
    cleaned = get_cleaned()
    if cleaned is None or cleaned.is_blocked or cleaned.dataframe.empty:
        _render_missing_dataset()
        return

    render_section(
        "Overview",
        "A consolidated view of revenue, orders, products and trends for the "
        "current selection. Every card and chart uses the same filtered rows.",
    )

    filter_state = render_dashboard_filters(cleaned)
    filtered = apply_filters(cleaned.dataframe, filter_state)
    metrics = compute_dashboard_metrics(
        cleaned.dataframe,
        filter_state,
        order_id_available=cleaned.order_id_available,
    )

    _render_period_context(
        metrics.current_period,
        metrics.previous_period,
        filtered_rows=len(filtered),
        total_rows=len(cleaned.dataframe),
        previous_rows=metrics.previous_rows,
    )

    comparisons = {comparison.key: comparison for comparison in metrics.comparisons}
    render_kpi_cards(
        comparisons,
        metrics.previous_period,
        order_id_available=cleaned.order_id_available,
    )

    if filtered.empty:
        st.warning(
            "No rows match the current filters. Widen the date range or clear one "
            "of the category, region, product or status filters."
        )

    render_section(
        "Revenue trend",
        "Zoom or pan the chart, then switch between daily, weekly and monthly aggregation.",
    )
    _render_trend(filtered, order_id_available=cleaned.order_id_available)

    render_section(
        "Where revenue comes from",
        "Category totals and the ten highest-revenue products in the selected period.",
    )
    _render_breakdowns(filtered)

    render_section(
        "Business insights",
        "Deterministic observations calculated from the filtered rows — no external "
        "models or AI services are used.",
    )
    insights = generate_insights(
        filtered,
        order_id_available=cleaned.order_id_available,
        max_items=3,
    )
    render_insight_cards(insights)

    if not cleaned.order_id_available:
        st.caption(
            "This dataset has no usable `order_id` column, so each row is counted "
            "as one order. Add order IDs to group multi-line orders accurately."
        )

    render_footer()
