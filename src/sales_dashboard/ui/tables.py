"""Reusable performance tables for the Products and Regions pages."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from sales_dashboard.formatting import format_inr, format_number


def _format_share(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):.1%}"


def _style_performance_table(
    display: pd.DataFrame,
    *,
    currency_columns: tuple[str, ...],
) -> pd.io.formats.style.Styler:
    formats: dict[str, object] = {
        "Units sold": lambda value: format_number(value),
        "Orders": lambda value: format_number(value),
        "Revenue share": _format_share,
    }
    for column in currency_columns:
        formats[column] = lambda value: format_inr(value)
    return display.style.format(formats)


def render_product_performance_table(data: pd.DataFrame) -> None:
    """Render the sortable product performance table."""
    if data.empty:
        st.info("No product revenue is available for the current filters.")
        return

    display = pd.DataFrame(
        {
            "Product": data["product"],
            "Revenue": data["revenue"],
            "Units sold": data["units"],
            "Orders": data["orders"],
            "Average order value": data["average_order_value"],
            "Revenue share": data["share"],
        }
    )
    st.dataframe(
        _style_performance_table(
            display,
            currency_columns=("Revenue", "Average order value"),
        ),
        width="stretch",
        hide_index=True,
    )
    st.caption("Click a column header to sort. Revenue share uses total net revenue as its base.")
    if data["share"].isna().all():
        st.caption(
            "Revenue share is unavailable because total net revenue is not positive "
            "for this selection."
        )


def render_region_performance_table(data: pd.DataFrame) -> None:
    """Render the sortable regional performance table."""
    if data.empty:
        st.info("No regional revenue is available for the current filters.")
        return

    display = pd.DataFrame(
        {
            "Region": data["region"],
            "Revenue": data["revenue"],
            "Orders": data["orders"],
            "Units sold": data["units"],
            "Average order value": data["average_order_value"],
            "Revenue share": data["share"],
        }
    )
    st.dataframe(
        _style_performance_table(
            display,
            currency_columns=("Revenue", "Average order value"),
        ),
        width="stretch",
        hide_index=True,
    )
    st.caption("Click a column header to sort. Revenue share uses total net revenue as its base.")
    if data["share"].isna().all():
        st.caption(
            "Revenue share is unavailable because total net revenue is not positive "
            "for this selection."
        )
