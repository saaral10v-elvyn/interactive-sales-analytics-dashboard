"""Presentation helpers for dashboard KPI cards and insight statements."""

from __future__ import annotations

import html
from datetime import date

import streamlit as st

from sales_dashboard.analytics import KPI_CURRENCY, KPI_KEYS, KPI_LABELS
from sales_dashboard.formatting import format_date_range, format_inr, format_number
from sales_dashboard.models import Insight, KpiComparison

_INSIGHT_ICONS = {
    "category": "🏷️",
    "product": "📦",
    "trend": "📈",
    "coverage": "🧾",
}
_KPI_BASE_NOTES = {
    "total_revenue": "Net of discounts and returns",
    "average_order_value": "Net revenue ÷ orders",
    "total_units": "Includes returns",
    "total_products": "Distinct products",
}


def format_kpi_value(key: str, value: float) -> str:
    """Format one KPI using the application's currency rules."""
    if KPI_CURRENCY[key]:
        return format_inr(value, compact=True)
    return format_number(value)


def _format_absolute_change(key: str, value: float) -> str:
    if KPI_CURRENCY[key]:
        return format_inr(abs(value), compact=True)
    return format_number(abs(value))


def comparison_display(
    comparison: KpiComparison,
) -> tuple[str, str]:
    """Return the delta text and a CSS direction for a KPI card."""
    if not comparison.previous_available:
        return "No prior-period data", "flat"
    if comparison.absolute_change == 0:
        return "No change (0.0%)", "flat"

    direction = "up" if comparison.absolute_change > 0 else "down"
    arrow = "▲" if direction == "up" else "▼"
    change = _format_absolute_change(comparison.key, comparison.absolute_change)
    if comparison.percent_change is None:
        return f"{arrow} {change} · prior period was zero", direction
    return f"{arrow} {change} ({comparison.percent_change:+.1f}%)", direction


def render_kpi_card(
    key: str,
    comparison: KpiComparison,
    previous_period: tuple[date, date],
    *,
    order_id_available: bool,
) -> None:
    """Render one KPI card with its absolute and percentage change."""
    delta_text, direction = comparison_display(comparison)
    note = _KPI_BASE_NOTES.get(key, "")
    if key == "total_orders":
        note = "Distinct order_id" if order_id_available else "Each row = one order"

    comparison_label = format_date_range(previous_period[0], previous_period[1])
    note_html = f"vs {comparison_label}"
    if not comparison.previous_available:
        note_html = f"vs {comparison_label} · no data"

    st.markdown(
        f"""
        <div class="sa-metric">
            <div class="sa-metric-label">{html.escape(KPI_LABELS[key])}</div>
            <div class="sa-metric-value">{html.escape(format_kpi_value(key, comparison.current))}</div>
            <div class="sa-metric-delta sa-delta-{direction}">{html.escape(delta_text)}</div>
            <div class="sa-metric-note">{html.escape(note)}</div>
            <div class="sa-metric-note">{html.escape(note_html)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_cards(
    comparisons: dict[str, KpiComparison],
    previous_period: tuple[date, date],
    *,
    order_id_available: bool,
) -> None:
    """Render the five KPI cards in a responsive row."""
    columns = st.columns(5)
    for column, key in zip(columns, KPI_KEYS, strict=False):
        with column:
            render_kpi_card(
                key,
                comparisons[key],
                previous_period,
                order_id_available=order_id_available,
            )


def render_insight_cards(insights: tuple[Insight, ...]) -> None:
    """Render deterministic insight statements as compact cards."""
    if not insights:
        st.info("There is not enough data to generate insights for this selection.")
        return

    columns = st.columns(len(insights))
    for column, insight in zip(columns, insights, strict=False):
        icon = _INSIGHT_ICONS.get(insight.kind, "💡")
        with column:
            st.markdown(
                f"""
                <div class="sa-insight">
                    <div class="sa-insight-icon">{icon}</div>
                    <div class="sa-insight-title">{html.escape(insight.title)}</div>
                    <div class="sa-insight-body">{html.escape(insight.body)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
