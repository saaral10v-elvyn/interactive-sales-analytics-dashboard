"""Tests for the pure dashboard filtering layer."""

from datetime import date

import pandas as pd
import pytest

from sales_dashboard.filters import (
    DEFAULT_DATE_PRESET,
    apply_filters,
    dataset_date_bounds,
    detect_preset,
    filter_options,
    filter_summary_lines,
    has_active_filters,
    preset_range,
    previous_period,
    resolve_filter_state,
    selected_filter_count,
    summarize_filters,
)
from sales_dashboard.models import FilterState


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "order_date": pd.to_datetime(
                [
                    "2025-12-31",
                    "2026-01-05",
                    "2026-01-10",
                    "2026-01-15",
                    "2026-02-01",
                    "2026-03-15",
                ]
            ),
            "order_id": ["A", "B", "C", "D", "E", "F"],
            "product": ["Pen", "Pad", "Pen", "Lamp", "Pad", "Desk"],
            "category": ["Office", "Office", "Office", "Home", "Home", "Home"],
            "region": ["North", "South", "North", "East", "South", "East"],
            "status": ["Completed", "Completed", "Pending", "Completed", "Returned", "Pending"],
            "quantity": [1, 2, 3, 4, 5, 6],
            "revenue": [10.0, 40.0, 30.0, 80.0, 100.0, 180.0],
        }
    )


def test_dataset_date_bounds_uses_real_dates() -> None:
    assert dataset_date_bounds(_frame()) == (date(2025, 12, 31), date(2026, 3, 15))


def test_dataset_date_bounds_handles_empty_and_missing_columns() -> None:
    assert dataset_date_bounds(pd.DataFrame()) is None
    assert dataset_date_bounds(pd.DataFrame({"revenue": [1.0]})) is None
    assert dataset_date_bounds(pd.DataFrame({"order_date": [None]})) is None


@pytest.mark.parametrize(
    ("preset", "expected_start"),
    [
        ("all_time", date(2025, 12, 31)),
        ("last_7_days", date(2026, 3, 9)),
        ("last_30_days", date(2026, 2, 14)),
        ("last_90_days", date(2025, 12, 31)),
        ("this_month", date(2026, 3, 1)),
        ("this_year", date(2026, 1, 1)),
        ("custom", date(2025, 12, 31)),
    ],
)
def test_presets_anchor_to_dataset_max_date(preset, expected_start) -> None:
    start, end = preset_range(preset, date(2025, 12, 31), date(2026, 3, 15))

    assert start == expected_start
    assert end == date(2026, 3, 15)


def test_presets_are_clamped_to_the_dataset_minimum() -> None:
    start, end = preset_range("last_90_days", date(2026, 3, 1), date(2026, 3, 15))

    assert start == date(2026, 3, 1)
    assert end == date(2026, 3, 15)


def test_default_preset_is_last_ninety_days() -> None:
    assert DEFAULT_DATE_PRESET == "last_90_days"


def test_detect_preset_round_trips_and_falls_back_to_custom() -> None:
    bounds = (date(2025, 12, 31), date(2026, 3, 15))

    for preset in ("all_time", "last_7_days", "last_30_days", "this_month", "this_year"):
        start, end = preset_range(preset, *bounds)
        assert detect_preset(start, end, *bounds) == preset

    assert detect_preset(date(2026, 2, 1), date(2026, 2, 10), *bounds) == "custom"


def test_previous_period_is_equal_length_and_immediately_before() -> None:
    assert previous_period(date(2026, 1, 10), date(2026, 1, 16)) == (
        date(2026, 1, 3),
        date(2026, 1, 9),
    )
    assert previous_period(date(2026, 1, 10), date(2026, 1, 10)) == (
        date(2026, 1, 9),
        date(2026, 1, 9),
    )


def test_filter_options_are_sorted_and_ignore_blanks() -> None:
    dataframe = pd.DataFrame(
        {
            "category": ["Home", "Office", " ", None],
            "region": ["South", "North", "East", None],
            "product": ["Pen", "Pen", "Lamp", None],
            "status": [None, "Completed", "Pending", ""],
        }
    )

    options = filter_options(dataframe)

    assert options["category"] == ("Home", "Office")
    assert options["region"] == ("East", "North", "South")
    assert options["product"] == ("Lamp", "Pen")
    assert options["status"] == ("Completed", "Pending")


def test_filter_options_skip_columns_that_do_not_exist() -> None:
    options = filter_options(pd.DataFrame({"order_date": ["2026-01-01"]}))

    assert options == {}


def _state(**overrides) -> FilterState:
    base = {
        "start_date": date(2025, 12, 31),
        "end_date": date(2026, 3, 15),
        "preset": "all_time",
        "categories": (),
        "regions": (),
        "products": (),
        "statuses": (),
    }
    base.update(overrides)
    return FilterState(**base)


def test_apply_filters_by_date_range() -> None:
    filtered = apply_filters(
        _frame(),
        _state(start_date=date(2026, 1, 5), end_date=date(2026, 1, 15), preset="custom"),
    )

    assert filtered["order_id"].tolist() == ["B", "C", "D"]


def test_apply_filters_by_each_dimension() -> None:
    dataframe = _frame()

    assert apply_filters(dataframe, _state(categories=("Home",)))["order_id"].tolist() == [
        "D",
        "E",
        "F",
    ]
    assert apply_filters(dataframe, _state(regions=("South",)))["order_id"].tolist() == [
        "B",
        "E",
    ]
    assert apply_filters(dataframe, _state(products=("Pen",)))["order_id"].tolist() == [
        "A",
        "C",
    ]
    assert apply_filters(dataframe, _state(statuses=("Pending",)))["order_id"].tolist() == [
        "C",
        "F",
    ]


def test_apply_filters_combines_every_condition() -> None:
    state = _state(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 15),
        preset="custom",
        categories=("Home",),
        regions=("East",),
        products=("Desk",),
        statuses=("Pending",),
    )

    filtered = apply_filters(_frame(), state)

    assert filtered["order_id"].tolist() == ["F"]


def test_apply_filters_with_missing_dimension_does_not_drop_rows() -> None:
    dataframe = pd.DataFrame(
        {
            "order_date": pd.to_datetime(["2026-01-01"]),
            "revenue": [10.0],
        }
    )

    filtered = apply_filters(dataframe, _state(statuses=("Completed",)))

    assert len(filtered) == 1


def test_resolve_filter_state_clamps_dates_and_drops_stale_selections() -> None:
    state = _state(
        start_date=date(2020, 1, 1),
        end_date=date(2030, 1, 1),
        preset="custom",
        categories=("Home", "Retired"),
        regions=("South",),
    )

    resolved = resolve_filter_state(_frame(), state)

    assert resolved.start_date == date(2025, 12, 31)
    assert resolved.end_date == date(2026, 3, 15)
    assert resolved.preset == "all_time"
    assert resolved.categories == ("Home",)
    assert resolved.regions == ("South",)


def test_resolve_filter_state_swaps_reversed_dates() -> None:
    state = _state(start_date=date(2026, 3, 1), end_date=date(2026, 1, 1))

    resolved = resolve_filter_state(_frame(), state)

    assert resolved.start_date == date(2026, 1, 1)
    assert resolved.end_date == date(2026, 3, 1)


def test_summaries_describe_active_filters() -> None:
    state = _state(
        start_date=date(2026, 1, 5),
        end_date=date(2026, 1, 15),
        preset="custom",
        categories=("Home",),
        regions=("South",),
        products=("Pen",),
    )

    assert selected_filter_count(state) == 3
    assert has_active_filters(state, date(2025, 12, 31), date(2026, 3, 15)) is True
    summary = summarize_filters(state)
    assert "Custom" in summary
    assert "Home" in summary
    assert "South" in summary
    assert "Pen" in summary
    assert "statuses" not in summary

    lines = filter_summary_lines(state)
    assert lines["Categories"] == "Home"
    assert lines["Regions"] == "South"
    assert lines["Products"] == "Pen"
    assert lines["Statuses"] == "All statuses"


def test_summarize_filters_uses_all_dates_and_plural_labels() -> None:
    state = _state(categories=("Home", "Office", "Other"))

    summary = summarize_filters(state)

    assert summary.startswith("All dates")
    assert "3 categories" in summary


def test_all_time_state_has_no_active_filters() -> None:
    state = _state()

    assert selected_filter_count(state) == 0
    assert has_active_filters(state, date(2025, 12, 31), date(2026, 3, 15)) is False
