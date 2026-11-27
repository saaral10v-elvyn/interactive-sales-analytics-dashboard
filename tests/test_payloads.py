"""Unit tests for the JSON serialisers shared with the parity fixtures."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

from sales_dashboard.models import (
    CleanedDataset,
    ColumnMapping,
    DatasetProfile,
    ValidationReport,
)
from sales_dashboard.payloads import cleaning_summary, jsonable, records


@pytest.mark.parametrize("value", [None, pd.NaT, pd.NA])
def test_missing_values_become_null(value: object) -> None:
    assert jsonable(value) is None


def test_dataframe_and_series_become_json_rows() -> None:
    frame = pd.DataFrame(
        {
            0: [1, 2],
            "label": ["a", None],
            "amount": [1.23456789, np.float64("nan")],
        }
    )

    assert jsonable(frame) == [
        {"0": 1, "label": "a", "amount": 1.234568},
        {"0": 2, "label": None, "amount": None},
    ]
    assert jsonable(pd.Series([1, 2])) == [1, 2]


def test_records_stringifies_column_names() -> None:
    frame = pd.DataFrame({0: [1], 12: ["x"]})

    assert records(frame) == [{"0": 1, "12": "x"}]


def test_dates_and_timestamps_use_iso_format() -> None:
    assert jsonable(date(2026, 5, 1)) == "2026-05-01"
    assert jsonable(datetime(2026, 5, 1, 9, 30)) == "2026-05-01T09:30:00"
    assert jsonable(pd.Timestamp("2026-05-01T09:30:00")) == "2026-05-01T09:30:00"
    assert jsonable(pd.Timestamp("NaT")) is None


def test_scalars_keep_their_types() -> None:
    assert jsonable(True) is True
    assert jsonable(np.bool_(False)) is False
    assert jsonable(7) == 7
    assert jsonable(np.int64(7)) == 7
    assert jsonable(np.float64(1.5)) == 1.5
    assert jsonable("text") == "text"


def test_floats_are_rounded_and_unsafe_values_become_null() -> None:
    assert jsonable(2.0 / 3.0) == 0.666667
    assert jsonable(-1e-9) == 0.0
    assert jsonable(float("inf")) is None
    assert jsonable(float("-inf")) is None
    assert jsonable(float("nan")) is None


def test_dataclasses_mappings_and_sequences_are_flattened() -> None:
    profile = DatasetProfile(
        row_count=2,
        column_count=3,
        missing_cells=0,
        duplicate_rows=1,
        date_min=date(2026, 1, 1),
    )
    assert jsonable(profile) == {
        "row_count": 2,
        "column_count": 3,
        "missing_cells": 0,
        "duplicate_rows": 1,
        "date_min": "2026-01-01",
        "date_max": None,
        "order_count": None,
        "product_count": None,
        "category_count": None,
        "region_count": None,
        "net_revenue": None,
    }
    assert jsonable({1: (2, 3)}) == {"1": [2, 3]}
    assert jsonable({1, 2}) in ([1, 2], [2, 1])
    assert jsonable(dataclasses.asdict(profile))["date_min"] == "2026-01-01"


def test_unknown_types_fail_loudly() -> None:
    with pytest.raises(TypeError, match="Cannot serialise object"):
        jsonable(object())


def test_cleaning_summary_counts_kept_returns() -> None:
    report = ValidationReport(issues=(), rows_input=2, rows_output=2, rows_dropped=0)
    cleaned = CleanedDataset(
        dataframe=pd.DataFrame({"quantity": [2.0, -1.0], "revenue": [20.0, -10.0]}),
        mapping=ColumnMapping(fields={}),
        report=report,
        source_filename="sample.csv",
        revenue_source="line_total",
        date_format_used="DMY",
    )

    summary = cleaning_summary(cleaned)

    assert summary["rows"] == 2
    assert summary["returns_kept"] == 1
    assert summary["revenue_source"] == "line_total"
    assert summary["date_format_used"] == "DMY"
    assert summary["report"]["rows_output"] == 2


def test_cleaning_summary_handles_an_empty_frame() -> None:
    report = ValidationReport(issues=(), rows_input=0, rows_output=0, rows_dropped=0)
    cleaned = CleanedDataset(
        dataframe=pd.DataFrame({"quantity": pd.Series(dtype="float64")}),
        mapping=ColumnMapping(fields={}),
        report=report,
        source_filename="empty.csv",
    )

    assert cleaning_summary(cleaned)["returns_kept"] == 0


def test_cleaning_summary_without_a_quantity_column() -> None:
    report = ValidationReport(issues=(), rows_input=1, rows_output=1, rows_dropped=0)
    cleaned = CleanedDataset(
        dataframe=pd.DataFrame({"product": ["Alpha"]}),
        mapping=ColumnMapping(fields={}),
        report=report,
        source_filename="minimal.csv",
    )

    assert cleaning_summary(cleaned)["returns_kept"] == 0
