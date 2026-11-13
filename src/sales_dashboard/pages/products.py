"""Products page: performance table, Pareto analysis and product drill-down."""

from __future__ import annotations

import streamlit as st

from sales_dashboard.analytics import (
    pareto_threshold,
    product_pareto,
    product_performance,
    product_revenue_trend,
    product_snapshot,
    top_products,
)
from sales_dashboard.filters import apply_filters, summarize_filters
from sales_dashboard.formatting import format_date_range, format_inr, format_number
from sales_dashboard.models import TrendGranularity
from sales_dashboard.state import get_cleaned
from sales_dashboard.ui.charts import (
    PLOTLY_CONFIG,
    build_product_pareto_figure,
    build_revenue_trend_figure,
    build_top_products_figure,
)
from sales_dashboard.ui.filters import render_dashboard_filters
from sales_dashboard.ui.layout import render_footer, render_metric_card, render_section
from sales_dashboard.ui.tables import render_product_performance_table

_GRANULARITY_OPTIONS: dict[str, TrendGranularity] = {
    "Daily": "daily",
    "Weekly": "weekly",
    "Monthly": "monthly",
}
_DEFAULT_GRANULARITY = "Monthly"


def _render_missing_dataset() -> None:
    st.info(
        "The Products page needs a cleaned dataset. Load a CSV on the Home page, "
        "then run **Validate and clean data** to unlock the dashboard."
    )
    render_footer()


def _render_context(filter_state, *, filtered_rows: int, total_rows: int) -> None:
    st.caption(
        f"Selected period: **{format_date_range(filter_state.start_date, filter_state.end_date)}** · "
        f"{format_number(filtered_rows)} of {format_number(total_rows)} cleaned rows · "
        f"{summarize_filters(filter_state)}"
    )


def _render_drilldown(filtered, *, order_id_available: bool, products: list[str]) -> None:
    render_section(
        "Product drill-down",
        "Choose one product to inspect its headline metrics and revenue trend.",
    )
    if not products:
        st.info(
            "No product is available for the current filters, so there is nothing to drill into."
        )
        return

    key = "product_drilldown"
    if st.session_state.get(key) not in products:
        st.session_state[key] = products[0]

    selected = st.selectbox(
        "Choose a product",
        options=products,
        key=key,
        persist_state="session",
    )
    snapshot = product_snapshot(
        filtered,
        selected,
        order_id_available=order_id_available,
    )

    columns = st.columns(4)
    with columns[0]:
        render_metric_card(
            "Revenue",
            format_inr(snapshot.total_revenue, compact=True),
            "Net of discounts and returns",
        )
    with columns[1]:
        render_metric_card(
            "Units sold",
            format_number(snapshot.total_units),
            "Includes returns",
        )
    with columns[2]:
        render_metric_card(
            "Orders",
            format_number(snapshot.total_orders),
            "Distinct order_id" if order_id_available else "Each row = one order",
        )
    with columns[3]:
        render_metric_card(
            "Average order value",
            format_inr(snapshot.average_order_value, compact=True),
            "Net revenue ÷ orders",
        )

    granularity_label = st.segmented_control(
        "Trend granularity",
        options=list(_GRANULARITY_OPTIONS),
        default=_DEFAULT_GRANULARITY,
        key="product_granularity",
        help="Change how this product's revenue is grouped along the time axis.",
        persist_state="session",
    )
    label = granularity_label or _DEFAULT_GRANULARITY
    granularity = _GRANULARITY_OPTIONS[label]
    trend = product_revenue_trend(
        filtered,
        selected,
        granularity,
        order_id_available=order_id_available,
    )
    figure = build_revenue_trend_figure(
        trend,
        granularity,
        title=f"{selected} revenue trend",
    )
    if figure is None:
        st.info(
            "This product has no dated rows in the current selection, so no trend is available."
        )
    else:
        st.plotly_chart(figure, width="stretch", config=PLOTLY_CONFIG)


def render() -> None:
    """Render the Products analytics page."""
    cleaned = get_cleaned()
    if cleaned is None or cleaned.is_blocked or cleaned.dataframe.empty:
        _render_missing_dataset()
        return

    render_section(
        "Products",
        "Product-level revenue, order counts and concentration for the current selection. "
        "Every table and chart uses the same globally filtered rows.",
    )

    filter_state = render_dashboard_filters(cleaned)
    filtered = apply_filters(cleaned.dataframe, filter_state)
    _render_context(
        filter_state,
        filtered_rows=len(filtered),
        total_rows=len(cleaned.dataframe),
    )

    if filtered.empty:
        st.warning(
            "No rows match the current filters. Widen the date range or clear one "
            "of the category, region, product or status filters."
        )

    performance = product_performance(
        filtered,
        order_id_available=cleaned.order_id_available,
    )

    render_section(
        "Product performance",
        "Revenue, units, orders, average order value and revenue share for each product.",
    )
    render_product_performance_table(performance)

    render_section(
        "Top 10 products by revenue",
        "The highest-revenue products in the selected period.",
    )
    top_data = top_products(
        filtered,
        limit=10,
        order_id_available=cleaned.order_id_available,
    )
    top_figure = build_top_products_figure(top_data)
    if top_figure is None:
        st.info("No products match the current filters, so the ranking is empty.")
    else:
        st.plotly_chart(top_figure, width="stretch", config=PLOTLY_CONFIG)

    render_section(
        "Pareto analysis",
        "Products ranked by revenue, with cumulative contribution and the 80% threshold.",
    )
    pareto = product_pareto(
        filtered,
        order_id_available=cleaned.order_id_available,
    )
    threshold = pareto_threshold(pareto)
    pareto_figure = build_product_pareto_figure(pareto, threshold)
    if pareto_figure is None:
        if filtered.empty:
            st.info("No rows match the current filters, so Pareto analysis is unavailable.")
        else:
            st.info(
                "Pareto analysis needs positive net product revenue. This selection "
                "has none, so percentages would be misleading."
            )
    else:
        st.plotly_chart(pareto_figure, width="stretch", config=PLOTLY_CONFIG)
        if threshold is not None:
            st.caption(
                f"**80% threshold:** {threshold.product} is the first product to reach it "
                f"(rank {threshold.rank}, {threshold.cumulative_share:.1%} cumulative). "
                "Products with zero or negative net revenue are excluded."
            )

    products = performance["product"].astype(str).tolist() if not performance.empty else []
    _render_drilldown(
        filtered,
        order_id_available=cleaned.order_id_available,
        products=products,
    )

    if not cleaned.order_id_available:
        st.caption(
            "This dataset has no usable `order_id` column, so each row is counted "
            "as one order in the product metrics."
        )

    render_footer()
