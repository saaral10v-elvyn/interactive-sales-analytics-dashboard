"""Tests for date-axis ticks and explicit chart tick labels."""

import pandas as pd

from sales_dashboard.ui.charts import (
    build_regional_trend_figure,
    build_revenue_trend_figure,
    date_axis_range,
    date_tick_values,
)


def test_monthly_ticks_are_unique_and_formatted() -> None:
    periods = pd.Series(pd.to_datetime(["2026-08-01", "2026-09-01", "2026-10-01"]))

    values, labels = date_tick_values(periods, "monthly")

    assert labels == ["Aug 2026", "Sep 2026", "Oct 2026"]
    assert len(values) == 3


def test_daily_ticks_are_sampled_to_keep_the_axis_readable() -> None:
    periods = pd.Series(pd.date_range("2026-01-01", periods=120, freq="D"))

    values, labels = date_tick_values(periods, "daily")

    assert 1 < len(values) <= 9
    assert len(set(labels)) == len(labels)
    assert labels[0] == "01 Jan"


def test_blank_periods_produce_no_ticks() -> None:
    assert date_tick_values(pd.Series([], dtype="datetime64[ns]"), "monthly") == ([], [])


def test_date_axis_range_pads_each_granularity() -> None:
    periods = pd.Series(pd.to_datetime(["2026-08-01", "2026-09-01", "2026-10-01"]))

    monthly = date_axis_range(periods, "monthly")
    assert monthly == [
        pd.Timestamp("2026-07-17"),
        pd.Timestamp("2026-10-16"),
    ]

    assert date_axis_range(pd.Series([], dtype="datetime64[ns]"), "daily") is None


def test_revenue_and_regional_trends_use_explicit_month_labels() -> None:
    periods = pd.to_datetime(["2026-08-01", "2026-09-01", "2026-10-01"])
    trend = pd.DataFrame(
        {
            "period": periods,
            "revenue": [1000.0, 1500.0, 2000.0],
            "orders": [10, 12, 14],
            "units": [20, 24, 28],
        }
    )

    revenue_figure = build_revenue_trend_figure(trend, "monthly")
    assert list(revenue_figure.layout.xaxis.ticktext) == ["Aug 2026", "Sep 2026", "Oct 2026"]

    regional = pd.DataFrame(
        [
            {"period": period, "region": region, "revenue": revenue}
            for period, revenue in zip(periods, [400.0, 500.0, 600.0], strict=True)
            for region in ("North", "South")
        ]
    )
    regional_figure = build_regional_trend_figure(regional, "monthly")
    assert list(regional_figure.layout.xaxis.ticktext) == ["Aug 2026", "Sep 2026", "Oct 2026"]
