"""Tests for regional performance, category mix and regional trends."""

import pandas as pd
import pytest

from sales_dashboard.analytics import (
    region_category_revenue,
    regional_performance,
    regional_revenue_trend,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "order_id": ["O1", "O1", "O2", "O3", "O4"],
            "order_date": pd.to_datetime(
                [
                    "2026-01-01",
                    "2026-01-02",
                    "2026-01-03",
                    "2026-03-01",
                    "2026-03-02",
                ]
            ),
            "region": ["North", "North", "South", "", None],
            "category": ["Electronics", "Home", "Electronics", "Home", ""],
            "quantity": [1, 2, 1, 1, 1],
            "revenue": [100.0, 50.0, 200.0, 25.0, 75.0],
        }
    )


def test_regional_performance_calculates_metrics_and_handles_blank_regions() -> None:
    result = regional_performance(_frame(), order_id_available=True)

    assert result["region"].tolist() == ["South", "North", "Unknown region"]
    assert result["revenue"].tolist() == [200.0, 150.0, 100.0]
    assert result["orders"].tolist() == [1, 1, 2]
    assert result["units"].tolist() == [1.0, 3.0, 2.0]
    assert result["average_order_value"].tolist() == pytest.approx([200.0, 150.0, 50.0])
    assert result["share"].tolist() == pytest.approx([200 / 450, 150 / 450, 100 / 450])


def test_regional_performance_counts_blank_order_ids_separately() -> None:
    dataframe = pd.DataFrame(
        {
            "order_id": pd.Series(["O1", "", None], dtype="string"),
            "region": ["North", "North", "North"],
            "quantity": [1, 1, 1],
            "revenue": [10.0, 20.0, 30.0],
        }
    )

    result = regional_performance(dataframe, order_id_available=True)

    assert result.loc[0, "orders"] == 3
    assert result.loc[0, "average_order_value"] == 20.0


def test_regional_performance_falls_back_to_rows_without_order_ids() -> None:
    dataframe = _frame().drop(columns=["order_id"])

    result = regional_performance(dataframe, order_id_available=False)

    assert result.set_index("region").loc["North", "orders"] == 2
    assert result.set_index("region").loc["Unknown region", "orders"] == 2


def test_regional_performance_is_empty_without_a_region_column() -> None:
    assert regional_performance(pd.DataFrame({"revenue": [10.0]})).empty


def test_regional_share_is_undefined_for_zero_or_negative_total() -> None:
    for revenues in ([0.0, 0.0], [100.0, -200.0]):
        result = regional_performance(
            pd.DataFrame({"region": ["North", "South"], "revenue": revenues})
        )

        assert result["share"].isna().all()


def test_region_category_revenue_groups_blanks_and_totals() -> None:
    result = region_category_revenue(_frame())

    values = {(row.region, row.category): row.revenue for row in result.itertuples(index=False)}
    assert values[("North", "Electronics")] == 100.0
    assert values[("North", "Home")] == 50.0
    assert values[("South", "Electronics")] == 200.0
    assert values[("Unknown region", "Home")] == 25.0
    assert values[("Unknown region", "Uncategorised")] == 75.0
    assert len(result) == 5


def test_region_category_revenue_requires_region_and_category_columns() -> None:
    assert region_category_revenue(pd.DataFrame({"region": ["North"], "revenue": [1.0]})).empty
    assert region_category_revenue(pd.DataFrame({"category": ["Home"], "revenue": [1.0]})).empty


def test_regional_revenue_trend_fills_missing_periods_per_region() -> None:
    result = regional_revenue_trend(_frame(), "monthly")

    pivot = result.pivot(index="period", columns="region", values="revenue").fillna(0.0)
    pivot.index = pivot.index.strftime("%Y-%m")

    assert len(pivot) == 3
    assert pivot.index.tolist() == ["2026-01", "2026-02", "2026-03"]
    assert pivot.loc["2026-01", "North"] == 150.0
    assert pivot.loc["2026-02", "North"] == 0.0
    assert pivot.loc["2026-03", "North"] == 0.0
    assert pivot.loc["2026-01", "South"] == 200.0
    assert pivot.loc["2026-02", "South"] == 0.0
    assert pivot.loc["2026-03", "Unknown region"] == 100.0


def test_regional_revenue_trend_handles_missing_columns_and_empty_data() -> None:
    assert regional_revenue_trend(pd.DataFrame()).empty
    assert regional_revenue_trend(pd.DataFrame({"region": ["North"]})).empty
    assert regional_revenue_trend(
        pd.DataFrame({"order_date": pd.to_datetime(["2026-01-01"]), "revenue": [10.0]})
    ).empty
