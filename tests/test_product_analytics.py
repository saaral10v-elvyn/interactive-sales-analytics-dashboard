"""Tests for product performance, Pareto analysis and drill-down metrics."""

import pandas as pd
import pytest

from sales_dashboard.analytics import (
    pareto_threshold,
    product_pareto,
    product_performance,
    product_revenue_trend,
    product_snapshot,
    top_products,
)
from sales_dashboard.ui.charts import build_product_pareto_figure, build_top_products_figure


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "order_id": ["O1", "O1", "O2", "O3", "O3", "O4"],
            "order_date": pd.to_datetime(
                [
                    "2026-01-01",
                    "2026-01-01",
                    "2026-01-02",
                    "2026-01-03",
                    "2026-01-03",
                    "2026-01-04",
                ]
            ),
            "product": ["A", "A", "B", "A", "B", "C"],
            "quantity": [1, 2, 1, 1, 1, 1],
            "revenue": [100.0, 50.0, 200.0, 25.0, 75.0, 30.0],
        }
    )


def test_product_performance_calculates_revenue_orders_units_aov_and_share() -> None:
    result = product_performance(_frame(), order_id_available=True)

    assert result["product"].tolist() == ["B", "A", "C"]
    assert result["revenue"].tolist() == [275.0, 175.0, 30.0]
    assert result["units"].tolist() == [2.0, 4.0, 1.0]
    assert result["orders"].tolist() == [2, 2, 1]
    assert result["average_order_value"].tolist() == pytest.approx([137.5, 87.5, 30.0])
    assert result["share"].tolist() == pytest.approx([275 / 480, 175 / 480, 30 / 480])


def test_product_performance_counts_blank_order_ids_as_separate_orders() -> None:
    dataframe = pd.DataFrame(
        {
            "order_id": pd.Series(["O1", "", None], dtype="string"),
            "product": ["A", "A", "A"],
            "quantity": [1, 1, 1],
            "revenue": [10.0, 20.0, 30.0],
        }
    )

    result = product_performance(dataframe, order_id_available=True)

    assert result.loc[0, "orders"] == 3
    assert result.loc[0, "average_order_value"] == 20.0


def test_product_performance_falls_back_to_rows_without_order_ids() -> None:
    dataframe = _frame().drop(columns=["order_id"])

    result = product_performance(dataframe, order_id_available=False)

    assert result.set_index("product").loc["A", "orders"] == 3
    assert result.set_index("product").loc["B", "orders"] == 2


def test_product_performance_excludes_blank_products_and_handles_missing_column() -> None:
    dataframe = pd.DataFrame(
        {
            "product": ["A", "", None],
            "quantity": [1, 2, 3],
            "revenue": [10.0, 20.0, 30.0],
        }
    )

    result = product_performance(dataframe)

    assert result["product"].tolist() == ["A"]
    assert result["revenue"].tolist() == [10.0]
    assert product_performance(pd.DataFrame({"revenue": [10.0]})).empty


def test_product_performance_share_is_undefined_for_zero_or_negative_total() -> None:
    for revenues in ([0.0, 0.0], [100.0, -200.0]):
        result = product_performance(pd.DataFrame({"product": ["A", "B"], "revenue": revenues}))

        assert result["share"].isna().all()


def test_top_products_limits_the_revenue_ranking_to_ten() -> None:
    dataframe = pd.DataFrame(
        {
            "product": [f"P{index:02d}" for index in range(12)],
            "quantity": [1] * 12,
            "revenue": [float(120 - index * 10) for index in range(12)],
        }
    )

    result = top_products(dataframe, limit=10)

    assert len(result) == 10
    assert result["product"].tolist() == [f"P{index:02d}" for index in range(10)]
    assert result["revenue"].is_monotonic_decreasing


def test_product_pareto_calculates_cumulative_percentages_and_threshold() -> None:
    result = product_pareto(_frame(), order_id_available=True)

    assert result["product"].tolist() == ["B", "A", "C"]
    assert result["rank"].tolist() == [1, 2, 3]
    assert result["cumulative_revenue"].tolist() == [275.0, 450.0, 480.0]
    assert result["cumulative_share"].tolist() == pytest.approx([275 / 480, 450 / 480, 1.0])

    threshold = pareto_threshold(result)

    assert threshold is not None
    assert threshold.product == "A"
    assert threshold.rank == 2
    assert threshold.cumulative_share == pytest.approx(450 / 480)


def test_product_pareto_excludes_non_positive_products() -> None:
    dataframe = pd.DataFrame(
        {
            "product": ["X", "Y", "Z"],
            "quantity": [1, 1, 1],
            "revenue": [100.0, 50.0, -30.0],
        }
    )

    result = product_pareto(dataframe)

    assert result["product"].tolist() == ["X", "Y"]
    assert result["cumulative_share"].iloc[-1] == pytest.approx(1.0)
    threshold = pareto_threshold(result)
    assert threshold is not None
    assert threshold.product == "Y"


def test_product_pareto_is_empty_when_total_revenue_is_zero_or_negative() -> None:
    for revenues in ([0.0, 0.0], [-10.0, -20.0]):
        result = product_pareto(pd.DataFrame({"product": ["A", "B"], "revenue": revenues}))

        assert result.empty
        assert pareto_threshold(result) is None


def test_product_snapshot_and_trend_respect_the_selected_product() -> None:
    dataframe = _frame()

    snapshot = product_snapshot(dataframe, "A", order_id_available=True)
    trend = product_revenue_trend(dataframe, "A", "daily", order_id_available=True)

    assert snapshot.total_revenue == 175.0
    assert snapshot.total_units == 4.0
    assert snapshot.total_orders == 2
    assert snapshot.average_order_value == pytest.approx(87.5)
    assert trend["period"].dt.strftime("%Y-%m-%d").tolist() == [
        "2026-01-01",
        "2026-01-02",
        "2026-01-03",
    ]
    assert trend["revenue"].tolist() == [150.0, 0.0, 25.0]
    assert trend["orders"].tolist() == [1, 0, 1]
    assert trend["units"].tolist() == [3.0, 0.0, 1.0]


def test_product_snapshot_handles_unknown_and_empty_products_safely() -> None:
    empty = product_snapshot(pd.DataFrame(), "A", order_id_available=False)
    missing = product_snapshot(_frame(), "Missing", order_id_available=True)

    assert empty.total_revenue == 0.0
    assert empty.average_order_value == 0.0
    assert missing.total_revenue == 0.0
    assert missing.average_order_value == 0.0
    assert product_revenue_trend(pd.DataFrame(), "A", "monthly", order_id_available=False).empty


def test_product_charts_build_from_pareto_and_ranking_data() -> None:
    pareto = product_pareto(_frame(), order_id_available=True)
    threshold = pareto_threshold(pareto)
    ranking = top_products(_frame(), limit=10, order_id_available=True)

    pareto_figure = build_product_pareto_figure(pareto, threshold)
    ranking_figure = build_top_products_figure(ranking)

    assert pareto_figure is not None
    assert len(pareto_figure.data) == 3
    assert ranking_figure is not None
    assert len(ranking_figure.data) == 1
