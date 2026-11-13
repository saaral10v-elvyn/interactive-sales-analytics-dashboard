"""Shared sidebar content."""

import html

import streamlit as st

from sales_dashboard.config import APP_SHORT_NAME, APP_VERSION
from sales_dashboard.formatting import format_inr, format_number
from sales_dashboard.state import get_cleaned, get_dataset
from sales_dashboard.ui.layout import inject_styles


def render_sidebar() -> None:
    """Render the brand, dataset status and a short project note."""
    inject_styles()
    with st.sidebar:
        st.markdown(
            f"""
            <div class="sa-sidebar-brand">
                <span>📊</span>
                <span>{html.escape(APP_SHORT_NAME)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("Portfolio analytics project")
        st.divider()

        dataset = get_dataset()
        if dataset is None:
            st.info("No dataset loaded yet. Start on the Home page.")
        else:
            st.success("Dataset ready")
            st.caption(dataset.filename)
            summary = [f"{format_number(dataset.profile.row_count)} rows"]
            if dataset.profile.net_revenue is not None:
                summary.append(format_inr(dataset.profile.net_revenue, compact=True))
            st.caption(" · ".join(summary))

            cleaned = get_cleaned()
            if cleaned is not None:
                cleaned_count = format_number(cleaned.report.rows_output)
                st.caption(f"Cleaned: {cleaned_count} usable rows")
                if cleaned.report.should_warn_about_drops:
                    st.caption("⚠️ More than 20% of rows removed")
                if cleaned.report.blocked:
                    st.caption("⚠️ Analysis blocked: no usable rows")

        st.divider()
        st.caption("Python · Pandas · Streamlit · Plotly")
        st.caption(f"Version {APP_VERSION}")
