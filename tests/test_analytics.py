"""Tests for revenue KPIs, comparisons, aggregations and insights."""

from datetime import date

import pandas as pd
import pytest

from sales_dashboard.analytics import (
    KPI_KEYS,
    category_revenue,
    compare_snapshots,
    compute_dashboard_metrics,
    compute_kpis,
    count_orders,
    generate_insights,
    percentage_change,
    revenue_trend,
    top_products,
)
from sales_dashboard.models import FilterState, KpiSnapshot


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "order_id": ["P1", "P2", "C1", "C2", "C2"],
            "order_date": pd.to_datetime(
                [
                    "2026-01-07",
                    "2026-01-09",
                    "2026-01-10",
                    "2026-01-12",
                    "2026-01-12",
                ]
            ),
            "product": ["A", "B", "A", "C", "D"],
            "category": ["Home", "Home", "Home", "Home", "Office"],
            "region": ["North", "South", "North", "East", "East"],
            "status": ["Completed", "Completed", "Completed", "Pending", "Pending"],
            "quantity": [1, 2, 3, 1, 2],
            "revenue": [100.0, 50.0, 200.0, 100.0, 50.0],
        }
    )


def _state(**overrides) -> FilterState:
    base = {
        "start_date": date(2026, 1, 10),
        "end_date": date(2026, 1, 12),
        "preset": "custom",
        "categories": (),
        "regions": (),
        "products": (),
        "statuses": (),
    }
    base.update(overrides)
    return FilterState(**base)


def test_kpi_formulas_use_distinct_orders_and_products() -> None:
    snapshot = compute_kpis(_frame(), order_id_available=True)

    assert snapshot.total_revenue == 500.0
    assert snapshot.total_orders == 4
    assert snapshot.total_units == 9.0
    assert snapshot.total_products == 4
    assert snapshot.average_order_value == 125.0
    assert snapshot.rows == 5


def test_count_orders_falls_back_to_rows_without_order_id() -> None:
    dataframe = _frame()

    assert count_orders(dataframe, order_id_available=False) == 5
    assert count_orders(dataframe.drop(columns=["order_id"]), order_id_available=True) == 5


def test_count_orders_counts_each_blank_order_id_separately() -> None:
    dataframe = pd.DataFrame(
        {
            "order_id": pd.Series(["A", "A", "", None, "B"], dtype="string"),
            "revenue": [1.0, 2.0, 3.0, 4.0, 5.0],
        }
    )

    assert count_orders(dataframe, order_id_available=True) == 4


def test_empty_dataframe_returns_zeroed_kpis_and_zero_aov() -> None:
    snapshot = compute_kpis(pd.DataFrame(), order_id_available=False)

    assert snapshot == KpiSnapshot(order_id_available=False)
    assert snapshot.average_order_value == 0.0


def test_snapshot_with_no_orders_has_zero_aov() -> None:
    snapshot = KpiSnapshot(total_revenue=500.0, total_orders=0)

    assert snapshot.average_order_value == 0.0


def test_percentage_change_handles_zero_negative_and_positive_bases() -> None:
    assert percentage_change(120.0, 100.0) == pytest.approx(20.0)
    assert percentage_change(80.0, 100.0) == pytest.approx(-20.0)
    assert percentage_change(50.0, -100.0) == pytest.approx(150.0)
    assert percentage_change(50.0, 0.0) is None


def test_compare_snapshots_covers_every_kpi() -> None:
    current = KpiSnapshot(
        total_revenue=350.0,
        total_orders=2,
        total_units=6.0,
        total_products=3,
    )
    previous = KpiSnapshot(
        total_revenue=150.0,
        total_orders=2,
        total_units=3.0,
        total_products=2,
    )

    comparisons = compare_snapshots(current, previous, previous_available=True)

    assert [comparison.key for comparison in comparisons] == list(KPI_KEYS)
    revenue = comparisons[0]
    assert revenue.absolute_change == 200.0
    assert revenue.percent_change == pytest.approx(133.333333)
    orders = comparisons[1]
    assert orders.absolute_change == 0.0
    assert orders.percent_change == 0.0
    assert all(comparison.previous_available for comparison in comparisons)


def test_compare_snapshots_marks_unavailable_previous_period() -> None:
    current = KpiSnapshot(total_revenue=100.0, total_orders=1)
    previous = KpiSnapshot()

    comparisons = compare_snapshots(current, previous, previous_available=False)

    assert all(not comparison.previous_available for comparison in comparisons)
    assert comparisons[0].percent_change is None


def test_dashboard_metrics_compare_with_the_preceding_equal_length_period() -> None:
    metrics = compute_dashboard_metrics(
        _frame(),
        _state(),
        order_id_available=True,
    )

    assert metrics.current_period == (date(2026, 1, 10), date(2026, 1, 12))
    assert metrics.previous_period == (date(2026, 1, 7), date(2026, 1, 9))
    assert metrics.current.total_revenue == 350.0
    assert metrics.current.total_orders == 2
    assert metrics.current.total_units == 6.0
    assert metrics.current.total_products == 3
    assert metrics.previous.total_revenue == 150.0
    assert metrics.previous.total_orders == 2
    assert metrics.previous_rows == 2
    assert metrics.comparison_for("total_revenue").absolute_change == 200.0
    assert metrics.comparison_for("total_revenue").percent_change == pytest.approx(133.333333)
    assert metrics.comparison_for("average_order_value").current == 175.0


def test_dashboard_metrics_apply_non_date_filters_to_both_periods() -> None:
    metrics = compute_dashboard_metrics(
        _frame(),
        _state(categories=("Home",)),
        order_id_available=True,
    )

    assert metrics.current.total_revenue == 300.0
    assert metrics.previous.total_revenue == 150.0


def test_dashboard_metrics_report_no_prior_data_safely() -> None:
    metrics = compute_dashboard_metrics(
        _frame(),
        _state(start_date=date(2026, 2, 1), end_date=date(2026, 2, 2)),
        order_id_available=True,
    )

    assert metrics.previous_rows == 0
    assert metrics.current.rows == 0
    assert metrics.comparison_for("total_revenue").previous_available is False
    assert metrics.comparison_for("total_revenue").percent_change is None


def test_revenue_trend_daily_fills_missing_days() -> None:
    trend = revenue_trend(_frame().iloc[2:], "daily", order_id_available=True)

    assert trend["period"].dt.strftime("%Y-%m-%d").tolist() == [
        "2026-01-10",
        "2026-01-11",
        "2026-01-12",
    ]
    assert trend["revenue"].tolist() == [200.0, 0.0, 150.0]
    assert trend["orders"].tolist() == [1, 0, 1]
    assert trend["units"].tolist() == [3.0, 0.0, 3.0]


def test_revenue_trend_weekly_groups_by_week_start() -> None:
    dataframe = pd.DataFrame(
        {
            "order_date": pd.to_datetime(["2026-01-05", "2026-01-12", "2026-01-20"]),
            "order_id": ["A", "B", "C"],
            "quantity": [1, 2, 3],
            "revenue": [100.0, 200.0, 50.0],
        }
    )

    trend = revenue_trend(dataframe, "weekly", order_id_available=True)

    assert trend["period"].dt.strftime("%Y-%m-%d").tolist() == [
        "2026-01-05",
        "2026-01-12",
        "2026-01-19",
    ]
    assert trend["revenue"].tolist() == [100.0, 200.0, 50.0]


def test_revenue_trend_monthly_fills_missing_months() -> None:
    dataframe = pd.DataFrame(
        {
            "order_date": pd.to_datetime(["2026-01-05", "2026-01-20", "2026-03-02"]),
            "quantity": [1, 1, 1],
            "revenue": [100.0, 50.0, 30.0],
        }
    )

    trend = revenue_trend(dataframe, "monthly", order_id_available=False)

    assert trend["period"].dt.strftime("%Y-%m").tolist() == ["2026-01", "2026-02", "2026-03"]
    assert trend["revenue"].tolist() == [150.0, 0.0, 30.0]
    assert trend["orders"].tolist() == [2, 0, 1]


def test_revenue_trend_returns_empty_frame_for_unusable_data() -> None:
    assert revenue_trend(pd.DataFrame(), "daily", order_id_available=True).empty
    assert revenue_trend(
        pd.DataFrame({"revenue": [10.0]}),
        "daily",
        order_id_available=True,
    ).empty


def test_category_revenue_calculates_totals_shares_and_uncategorised() -> None:
    dataframe = pd.DataFrame(
        {
            "category": ["Home", "Home", "Office", None],
            "quantity": [1, 2, 3, 4],
            "revenue": [100.0, 50.0, 75.0, 25.0],
        }
    )

    result = category_revenue(dataframe)

    assert result["category"].tolist() == ["Home", "Office", "Uncategorised"]
    assert result["revenue"].tolist() == [150.0, 75.0, 25.0]
    assert result["units"].tolist() == [3.0, 3.0, 4.0]
    assert result["share"].tolist() == pytest.approx([0.6, 0.3, 0.1])


def test_category_revenue_returns_empty_without_a_category_column() -> None:
    assert category_revenue(pd.DataFrame({"revenue": [10.0]})).empty


def test_top_products_aggregates_sorts_and_limits() -> None:
    dataframe = pd.DataFrame(
        {
            "product": ["A", "B", "A", "C", "", None],
            "quantity": [1, 1, 2, 3, 4, 5],
            "revenue": [100.0, 200.0, 50.0, 25.0, 999.0, 999.0],
        }
    )

    result = top_products(dataframe, limit=2)

    assert result["product"].tolist() == ["B", "A"]
    assert result["revenue"].tolist() == [200.0, 150.0]
    assert result["units"].tolist() == [1.0, 3.0]


def test_top_products_handles_zero_limit_and_missing_columns() -> None:
    assert top_products(_frame(), limit=0).empty
    assert top_products(pd.DataFrame({"revenue": [1.0]})).empty


def test_generate_insights_prioritises_category_product_and_trend() -> None:
    insights = generate_insights(_frame(), order_id_available=True)

    assert len(insights) == 3
    assert insights[0].title == "Home is the top category"
    assert insights[1].title == "A is the top product"
    assert insights[2].title == "Revenue is trending up"
    assert "₹" in insights[0].body


def test_generate_insights_falls_back_to_coverage_for_short_periods() -> None:
    dataframe = pd.DataFrame(
        {
            "order_date": pd.to_datetime(["2026-01-10", "2026-01-10"]),
            "order_id": ["A", "A"],
            "product": ["Pen", "Pad"],
            "category": ["Office", "Office"],
            "quantity": [1, 2],
            "revenue": [10.0, 20.0],
        }
    )

    insights = generate_insights(dataframe, order_id_available=True)

    assert [insight.kind for insight in insights] == ["category", "product", "coverage"]
    assert "2 line items" in insights[2].body
    assert "1 orders" in insights[2].body


def test_generate_insights_does_not_claim_positive_performance_for_negative_revenue() -> None:
    dataframe = pd.DataFrame(
        {
            "order_date": pd.to_datetime(["2026-01-01", "2026-01-02"]),
            "product": ["Pen", "Pad"],
            "category": ["Office", "Home"],
            "quantity": [-1, -2],
            "revenue": [-10.0, -20.0],
        }
    )

    insights = generate_insights(dataframe, order_id_available=False)

    titles = [insight.title for insight in insights]
    assert "No category generated positive revenue" in titles
    assert "No product generated positive revenue" in titles
    assert "Net revenue is negative for this selection" in titles
    assert not any("top category" in title.lower() for title in titles)


def test_generate_insights_for_empty_filtered_data_is_safe() -> None:
    insights = generate_insights(pd.DataFrame(), order_id_available=False)

    assert len(insights) == 1
    assert insights[0].kind == "coverage"
    assert "No rows" in insights[0].body


def test_generate_insights_respects_max_items() -> None:
    assert (
        generate_insights(_frame(), order_id_available=True, max_items=2)
        == generate_insights(
            _frame(),
            order_id_available=True,
        )[:2]
    )
    assert generate_insights(_frame(), order_id_available=True, max_items=0) == ()


def test_returns_reduce_revenue_and_units() -> None:
    dataframe = pd.DataFrame(
        {
            "order_id": ["A", "R1"],
            "quantity": [3, -1],
            "revenue": [300.0, -100.0],
        }
    )

    snapshot = compute_kpis(dataframe, order_id_available=True)

    assert snapshot.total_revenue == 200.0
    assert snapshot.total_units == 2.0
    assert snapshot.total_orders == 2
