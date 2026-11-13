"""Streamlit entry point for the Interactive Sales Analytics Dashboard."""

import logging
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import streamlit as st

from sales_dashboard.config import APP_NAME
from sales_dashboard.pages import explorer, home, overview, products, regions
from sales_dashboard.state import get_cleaned, init_state
from sales_dashboard.ui.errors import render_error_screen
from sales_dashboard.ui.sidebar import render_sidebar

logger = logging.getLogger(__name__)


def main() -> None:
    """Configure the page, shared sidebar and navigation."""
    st.set_page_config(
        page_title=APP_NAME,
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_state()
    render_sidebar()

    pages = [
        st.Page(home.render, title="Home", icon=":material/home:", default=True),
    ]

    cleaned = get_cleaned()
    if cleaned is not None and not cleaned.is_blocked and not cleaned.dataframe.empty:
        pages.extend(
            [
                st.Page(
                    overview.render,
                    title="Overview",
                    icon=":material/insights:",
                    url_path="overview",
                ),
                st.Page(
                    products.render,
                    title="Products",
                    icon=":material/inventory_2:",
                    url_path="products",
                ),
                st.Page(
                    regions.render,
                    title="Regions",
                    icon=":material/public:",
                    url_path="regions",
                ),
                st.Page(
                    explorer.render,
                    title="Data Explorer",
                    icon=":material/table_view:",
                    url_path="explorer",
                ),
            ]
        )

    navigation = st.navigation(pages)
    try:
        navigation.run()
    except Exception as exc:  # noqa: BLE001 - last-resort boundary for the whole page
        logger.exception("Unexpected error while rendering a page")
        render_error_screen(exc)


if __name__ == "__main__":
    main()
