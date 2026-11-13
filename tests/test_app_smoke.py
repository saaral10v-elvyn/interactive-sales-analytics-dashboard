"""End-to-end smoke tests for the Streamlit entry point."""

import json
from dataclasses import replace
from pathlib import Path

from streamlit.testing.v1 import AppTest


def _start_home_app(project_root: Path) -> AppTest:
    """Run the real app.py entry point once."""
    app = AppTest.from_file(str(project_root / "app.py"), default_timeout=60)
    app.run()
    return app


def _load_demo(app: AppTest) -> AppTest:
    next(button for button in app.button if button.label == "Load demo dataset").click().run()
    return app


def _clean_dataset(app: AppTest) -> AppTest:
    next(button for button in app.button if button.label == "Validate and clean data").click().run()
    return app


def _page_hash(app: AppTest, page_name: str) -> str:
    return next(
        page_hash
        for page_hash, page in app._registered_pages.items()  # noqa: SLF001
        if page["page_name"] == page_name
    )


def _open_page(app: AppTest, page_name: str) -> AppTest:
    """Select a programmatically registered page, as the sidebar would."""
    app._page_hash = _page_hash(app, page_name)  # noqa: SLF001
    app.run()
    return app


def _page_names(app: AppTest) -> set[str]:
    return {page["page_name"] for page in app._registered_pages.values()}  # noqa: SLF001


def _markdown_text(app: AppTest) -> str:
    return "\n".join(element.value for element in app.markdown)


def _load_clean_and_open_page(project_root: Path, page_name: str) -> AppTest:
    app = _start_home_app(project_root)
    _load_demo(app)
    _clean_dataset(app)
    return _open_page(app, page_name)


def _load_clean_and_open_overview(project_root: Path) -> AppTest:
    return _load_clean_and_open_page(project_root, "Overview")


def test_home_page_renders_without_exceptions(project_root: Path) -> None:
    app = _start_home_app(project_root)

    assert not app.exception
    labels = [button.label for button in app.button]
    assert "Load demo dataset" in labels
    assert "Load uploaded CSV" in labels


def test_demo_button_loads_the_bundled_dataset(project_root: Path) -> None:
    app = _start_home_app(project_root)

    next(button for button in app.button if button.label == "Load demo dataset").click().run()

    assert not app.exception
    dataset = app.session_state["loaded_dataset"]
    assert dataset is not None
    assert dataset.filename == "sales_demo.csv"
    assert dataset.profile.row_count > 1_000


def test_demo_dataset_can_be_validated_and_cleaned(project_root: Path) -> None:
    app = _start_home_app(project_root)
    next(button for button in app.button if button.label == "Load demo dataset").click().run()

    labels = [button.label for button in app.button]
    assert "Validate and clean data" in labels
    next(button for button in app.button if button.label == "Validate and clean data").click().run()

    assert not app.exception
    cleaned = app.session_state["cleaned_dataset"]
    assert cleaned is not None
    assert cleaned.report.rows_output > 1_000
    assert cleaned.report.blocked is False
    assert "revenue" in cleaned.dataframe.columns


def test_overview_navigation_appears_only_after_cleaning(project_root: Path) -> None:
    app = _start_home_app(project_root)

    assert _page_names(app) == {"Home"}

    _load_demo(app)
    assert _page_names(app) == {"Home"}

    _clean_dataset(app)
    assert _page_names(app) == {"Home", "Overview", "Products", "Regions", "Data Explorer"}
    paths = {
        page["page_name"]: page["url_pathname"]
        for page in app._registered_pages.values()  # noqa: SLF001
    }
    assert paths["Overview"] == "overview"
    assert paths["Products"] == "products"
    assert paths["Regions"] == "regions"
    assert paths["Data Explorer"] == "explorer"


def test_overview_renders_five_kpis_three_charts_and_insights(project_root: Path) -> None:
    app = _load_clean_and_open_overview(project_root)

    assert not app.exception
    text = _markdown_text(app)
    for label in (
        "Total revenue",
        "Total orders",
        "Average order value",
        "Total units sold",
        "Total products",
    ):
        assert label in text
    assert text.count('class="sa-metric"') == 5
    assert text.count('class="sa-insight"') == 3
    assert "vs " in text

    charts = app.get("plotly_chart")
    assert len(charts) == 3
    specs = [json.loads(chart.proto.spec) for chart in charts]
    assert all(spec["data"] for spec in specs)
    assert [spec["layout"]["title"]["text"] for spec in specs] == [
        "Revenue trend",
        "Revenue by category",
        "Top products by revenue",
    ]

    captions = [caption.value for caption in app.caption]
    assert any("Selected period" in caption for caption in captions)
    assert any("preceding equal-length period" in caption for caption in captions)


def test_default_filters_are_anchored_to_the_dataset_max_date(project_root: Path) -> None:
    app = _load_clean_and_open_overview(project_root)

    assert app.session_state["dash_preset"] == "last_90_days"
    assert app.session_state["dash_end"].isoformat() == "2026-10-31"
    assert app.session_state["dash_start"].isoformat() == "2026-08-03"


def test_shared_filters_persist_when_navigating_between_pages(project_root: Path) -> None:
    app = _load_clean_and_open_overview(project_root)
    next(element for element in app.multiselect if element.label == "Category").select(
        "Electronics"
    ).run()

    assert not app.exception
    assert app.session_state["dash_categories"] == ["Electronics"]
    filtered_caption = next(
        caption.value for caption in app.sidebar.caption if caption.value.startswith("Showing")
    )

    _open_page(app, "Home")
    assert not app.exception
    assert app.session_state["dash_categories"] == ["Electronics"]
    assert "Data-quality report" in _markdown_text(app)

    _open_page(app, "Overview")
    assert not app.exception
    assert app.session_state["dash_categories"] == ["Electronics"]
    assert filtered_caption in [caption.value for caption in app.sidebar.caption]


def test_reset_button_restores_default_filters(project_root: Path) -> None:
    app = _load_clean_and_open_overview(project_root)
    next(element for element in app.multiselect if element.label == "Category").select(
        "Electronics"
    ).run()
    app.selectbox[0].select("last_7_days").run()

    assert app.session_state["dash_preset"] == "last_7_days"
    assert app.session_state["dash_start"].isoformat() == "2026-10-25"

    next(button for button in app.button if button.label == "Reset all filters").click().run()

    assert not app.exception
    assert app.session_state["dash_categories"] == []
    assert app.session_state["dash_preset"] == "last_90_days"
    assert app.session_state["dash_start"].isoformat() == "2026-08-03"
    assert app.session_state["dash_end"].isoformat() == "2026-10-31"


def test_manual_date_change_keeps_a_custom_preset_label(project_root: Path) -> None:
    app = _load_clean_and_open_overview(project_root)
    new_start = app.session_state["dash_start"].replace(day=6)

    app.date_input[0].set_value(new_start).run()

    assert not app.exception
    assert app.session_state["dash_preset"] == "custom"
    assert app.selectbox[0].value == "custom"


def test_loading_a_new_dataset_resets_filters(project_root: Path) -> None:
    app = _load_clean_and_open_overview(project_root)
    next(element for element in app.multiselect if element.label == "Category").select(
        "Electronics"
    ).run()
    assert app.session_state["dash_categories"] == ["Electronics"]

    _open_page(app, "Home")
    _load_demo(app)

    assert not app.exception
    assert app.session_state["cleaned_dataset"] is None
    assert "dash_categories" not in app.session_state
    assert "dash_preset" not in app.session_state

    _clean_dataset(app)
    _open_page(app, "Overview")

    assert app.session_state["dash_categories"] == []
    assert app.session_state["dash_preset"] == "last_90_days"


def test_granularity_control_switches_the_revenue_trend(project_root: Path) -> None:
    app = _load_clean_and_open_overview(project_root)
    control = app.segmented_control[0]

    assert control.value == "Monthly"
    control.set_value("Weekly").run()

    assert not app.exception
    assert app.session_state["overview_granularity"] == "Weekly"
    assert len(app.get("plotly_chart")) == 3


def test_empty_filter_result_shows_friendly_empty_states(project_root: Path) -> None:
    app = _load_clean_and_open_overview(project_root)
    dataframe = app.session_state["cleaned_dataset"].dataframe

    category = "Electronics"
    unavailable_products = sorted(
        set(dataframe["product"].dropna())
        - set(dataframe.loc[dataframe["category"] == category, "product"].dropna())
    )
    assert unavailable_products

    next(element for element in app.multiselect if element.label == "Category").select(
        category
    ).run()
    next(element for element in app.multiselect if element.label == "Product").select(
        unavailable_products[0]
    ).run()

    assert not app.exception
    text = _markdown_text(app)
    assert "No rows match the current filters" in text
    info_text = "\n".join(element.value for element in app.info)
    assert "No dated rows match the current filters" in info_text
    assert "No products match the current filters" in info_text

    next(button for button in app.button if button.label == "Reset all filters").click().run()

    assert not app.exception
    assert "No rows match the current filters" not in _markdown_text(app)
    assert "No products match the current filters" not in "\n".join(
        element.value for element in app.info
    )


def test_products_page_renders_table_charts_and_drilldown(project_root: Path) -> None:
    app = _load_clean_and_open_page(project_root, "Products")

    assert not app.exception
    text = _markdown_text(app)
    assert "Product performance" in text
    assert "Pareto analysis" in text
    assert "Product drill-down" in text
    assert text.count('class="sa-metric"') == 4

    charts = app.get("plotly_chart")
    assert len(charts) == 3
    specs = [json.loads(chart.proto.spec) for chart in charts]
    selected = next(
        element for element in app.selectbox if element.label == "Choose a product"
    ).value
    assert [spec["layout"]["title"]["text"] for spec in specs] == [
        "Top products by revenue",
        "Pareto analysis: revenue concentration",
        f"{selected} revenue trend",
    ]
    assert len(app.get("dataframe")) == 1


def test_products_drilldown_can_change_product_and_granularity(project_root: Path) -> None:
    app = _load_clean_and_open_page(project_root, "Products")
    product_control = next(
        element for element in app.selectbox if element.label == "Choose a product"
    )
    target = product_control.options[-1]
    product_control.set_value(target).run()

    assert not app.exception
    assert app.session_state["product_drilldown"] == target
    assert _markdown_text(app).count('class="sa-metric"') == 4

    control = app.segmented_control[0]
    assert control.value == "Monthly"
    control.set_value("Weekly").run()

    assert not app.exception
    assert app.session_state["product_granularity"] == "Weekly"
    assert len(app.get("plotly_chart")) == 3


def test_regions_page_renders_table_and_three_charts(project_root: Path) -> None:
    app = _load_clean_and_open_page(project_root, "Regions")

    assert not app.exception
    text = _markdown_text(app)
    assert "Regional performance" in text
    assert "Category mix by region" in text
    assert "Regional revenue trend" in text

    charts = app.get("plotly_chart")
    assert len(charts) == 3
    specs = [json.loads(chart.proto.spec) for chart in charts]
    assert [spec["layout"]["title"]["text"] for spec in specs] == [
        "Revenue by region",
        "Category revenue by region",
        "Regional revenue trend",
    ]
    assert len(app.get("dataframe")) == 1


def test_filters_persist_across_products_and_regions_navigation(project_root: Path) -> None:
    app = _load_clean_and_open_page(project_root, "Products")
    next(element for element in app.multiselect if element.label == "Category").select(
        "Electronics"
    ).run()
    assert any(caption.value.startswith("Showing") for caption in app.sidebar.caption)

    _open_page(app, "Regions")
    assert not app.exception
    assert app.session_state["dash_categories"] == ["Electronics"]
    assert any("Electronics" in caption.value for caption in app.caption)

    _open_page(app, "Overview")
    assert not app.exception
    assert app.session_state["dash_categories"] == ["Electronics"]
    assert any("Electronics" in caption.value for caption in app.caption)


def test_products_and_regions_show_empty_states_without_rows(project_root: Path) -> None:
    app = _load_clean_and_open_page(project_root, "Products")
    dataframe = app.session_state["cleaned_dataset"].dataframe
    category = "Electronics"
    unavailable_products = sorted(
        set(dataframe["product"].dropna())
        - set(dataframe.loc[dataframe["category"] == category, "product"].dropna())
    )
    assert unavailable_products

    next(element for element in app.multiselect if element.label == "Category").select(
        category
    ).run()
    next(element for element in app.multiselect if element.label == "Product").select(
        unavailable_products[0]
    ).run()

    assert not app.exception
    products_info = "\n".join(element.value for element in app.info)
    assert "No product revenue is available" in products_info
    assert "No product is available" in products_info

    _open_page(app, "Regions")
    assert not app.exception
    regions_info = "\n".join(element.value for element in app.info)
    assert "No regional revenue is available" in regions_info
    assert "No dated regional revenue" in regions_info


def test_regions_page_explains_when_the_region_column_is_missing(project_root: Path) -> None:
    app = _load_clean_and_open_page(project_root, "Regions")
    cleaned = app.session_state["cleaned_dataset"]
    app.session_state["cleaned_dataset"] = replace(
        cleaned,
        dataframe=cleaned.dataframe.drop(columns=["region"]),
    )

    _open_page(app, "Regions")

    assert not app.exception
    info_text = "\n".join(element.value for element in app.info)
    assert "no `region` column" in info_text
    assert len(app.get("plotly_chart")) == 0


def test_data_explorer_renders_table_cards_and_downloads(project_root: Path) -> None:
    app = _load_clean_and_open_page(project_root, "Data Explorer")

    assert not app.exception
    text = _markdown_text(app)
    assert "Data Explorer" in text
    assert "Downloads" in text
    assert text.count('class="sa-metric"') == 4
    assert len(app.get("dataframe")) == 1
    assert app.get("dataframe")[0].value.shape[0] > 0

    labels = [button.label for button in app.get("download_button")]
    assert labels == [
        "Download filtered data (CSV)",
        "Download full cleaned data (CSV)",
        "Download quality report (CSV)",
    ]


def test_data_explorer_search_columns_and_row_limit_control_the_preview(
    project_root: Path,
) -> None:
    app = _load_clean_and_open_page(project_root, "Data Explorer")
    initial_rows = len(app.get("dataframe")[0].value)
    assert initial_rows == 100

    search = next(element for element in app.text_input if element.label == "Search rows")
    search.set_value("Coffee Maker").run()

    assert not app.exception
    filtered_rows = len(app.get("dataframe")[0].value)
    assert 0 < filtered_rows < initial_rows
    assert any("matching rows" in caption.value for caption in app.caption)

    columns = next(element for element in app.multiselect if element.label == "Columns to preview")
    columns.set_value(["product", "revenue"]).run()

    assert not app.exception
    assert list(app.get("dataframe")[0].value.columns) == ["product", "revenue"]

    limit = next(element for element in app.selectbox if element.label == "Rows to display")
    limit.set_value("25").run()

    assert not app.exception
    assert len(app.get("dataframe")[0].value) <= 25
    assert "Limit: 25" in _markdown_text(app)


def test_data_explorer_empty_search_shows_a_friendly_state(project_root: Path) -> None:
    app = _load_clean_and_open_page(project_root, "Data Explorer")
    search = next(element for element in app.text_input if element.label == "Search rows")
    search.set_value("no-such-product-xyz").run()

    assert not app.exception
    info_text = "\n".join(element.value for element in app.info)
    assert "No rows match" in info_text
    assert len(app.get("dataframe")) == 0


def test_data_explorer_respects_shared_filters(project_root: Path) -> None:
    app = _load_clean_and_open_page(project_root, "Overview")
    next(element for element in app.multiselect if element.label == "Category").select(
        "Electronics"
    ).run()

    _open_page(app, "Data Explorer")

    assert not app.exception
    caption = next(
        caption.value for caption in app.caption if caption.value.startswith("Selected period")
    )
    assert "Electronics" in caption
    assert "163 of 4,812 cleaned rows" in caption
    assert len(app.get("dataframe")) == 1


def test_home_offers_cleaned_data_and_quality_report_downloads(project_root: Path) -> None:
    app = _start_home_app(project_root)
    _load_demo(app)
    _clean_dataset(app)

    assert not app.exception
    labels = [button.label for button in app.get("download_button")]
    assert "Download sample CSV" in labels
    assert "Download cleaned data (CSV)" in labels
    assert "Download quality report (CSV)" in labels


def test_unexpected_page_error_shows_a_friendly_screen(project_root: Path, monkeypatch) -> None:
    from sales_dashboard.pages import home

    def boom() -> None:
        raise RuntimeError("simulated page failure")

    monkeypatch.setattr(home, "render", boom)

    app = _start_home_app(project_root)

    assert not app.exception
    error_text = "\n".join(element.value for element in app.error)
    assert "Something went wrong while drawing this page" in error_text
    expanders = [expander.label for expander in app.expander]
    assert "Technical details (for a bug report)" in expanders
    assert any(button.label == "Try again" for button in app.button)
