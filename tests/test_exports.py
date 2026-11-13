"""Tests for CSV exports and quality-report downloads."""

from datetime import datetime
from io import BytesIO

import pandas as pd
import pytest

from sales_dashboard.exports import (
    QUALITY_REPORT_COLUMNS,
    dataframe_to_csv_bytes,
    export_filename,
    quality_report_csv_bytes,
    quality_report_frame,
    select_columns,
)
from sales_dashboard.models import ValidationIssue, ValidationReport


def _report() -> ValidationReport:
    return ValidationReport(
        issues=(
            ValidationIssue(
                severity="warning",
                code="DUPLICATE_ROWS",
                description="Duplicate rows were removed.",
                affected_rows=3,
                action_taken="Kept the first copy.",
                examples=("ORD-1",),
            ),
            ValidationIssue(
                severity="info",
                code="MISSING_ORDER_ID",
                description="No order_id column was found.",
                affected_rows=0,
                action_taken="Each row counts as one order.",
            ),
        ),
        rows_input=100,
        rows_output=97,
        rows_dropped=3,
        date_format_used="auto",
    )


def test_dataframe_to_csv_bytes_round_trips_with_a_utf8_bom() -> None:
    dataframe = pd.DataFrame({"product": ["Café", "Chai"], "revenue": [1200.5, 800.0]})

    data = dataframe_to_csv_bytes(dataframe)

    assert data.startswith(b"\xef\xbb\xbf")
    restored = pd.read_csv(BytesIO(data), encoding="utf-8-sig")
    assert restored["product"].tolist() == ["Café", "Chai"]
    assert restored["revenue"].tolist() == [1200.5, 800.0]


def test_dataframe_to_csv_bytes_can_skip_the_bom() -> None:
    data = dataframe_to_csv_bytes(pd.DataFrame({"a": [1]}), bom=False)

    assert data == b"a\n1\n"


def test_export_filename_is_safe_and_timestamped() -> None:
    filename = export_filename(
        "My Sales (final).csv",
        "filtered data",
        timestamp=datetime(2026, 11, 13, 19, 30, 5),
    )

    assert filename == "My_Sales_final_filtered_data_20261113_193005.csv"


def test_export_filename_falls_back_for_empty_components() -> None:
    filename = export_filename(
        "",
        "***",
        timestamp=datetime(2026, 1, 2, 3, 4, 5),
    )

    assert filename == "sales_data_export_20260102_030405.csv"


def test_select_columns_preserves_order_and_validates_names() -> None:
    dataframe = pd.DataFrame({"a": [1], "b": [2], "c": [3]})

    selected = select_columns(dataframe, ["c", "a"])

    assert list(selected.columns) == ["c", "a"]
    assert selected.iloc[0].tolist() == [3, 1]

    with pytest.raises(ValueError):
        select_columns(dataframe, [])
    with pytest.raises(KeyError):
        select_columns(dataframe, ["a", "missing"])


def test_quality_report_frame_contains_summary_and_issue_rows() -> None:
    frame = quality_report_frame(
        _report(),
        source_filename="sales.csv",
        revenue_source="supplied line_total",
        date_format_used="DMY",
    )

    assert list(frame.columns) == list(QUALITY_REPORT_COLUMNS)
    summary = frame.loc[frame["Section"] == "Summary"].set_index("Code")["Value"]
    assert summary["source_file"] == "sales.csv"
    assert summary["rows_input"] == 100
    assert summary["rows_output"] == 97
    assert summary["rows_dropped"] == 3
    assert summary["dropped_ratio"] == "3.0%"
    assert summary["date_format"] == "DMY"
    assert summary["revenue_source"] == "supplied line_total"
    assert summary["issue_count"] == 2

    issues = frame.loc[frame["Section"] == "Issue"]
    assert issues["Code"].tolist() == ["DUPLICATE_ROWS", "MISSING_ORDER_ID"]
    assert issues["Severity"].tolist() == ["Warning", "Info"]
    assert issues["Affected rows"].tolist() == [3, 0]
    assert issues["Examples"].tolist() == ["ORD-1", "—"]


def test_quality_report_csv_bytes_is_downloadable_csv() -> None:
    data = quality_report_csv_bytes(
        _report(),
        source_filename="sales.csv",
        revenue_source="supplied line_total",
        date_format_used="auto",
    )

    assert data.startswith(b"\xef\xbb\xbf")
    restored = pd.read_csv(BytesIO(data), encoding="utf-8-sig")
    assert list(restored.columns) == list(QUALITY_REPORT_COLUMNS)
    assert set(restored["Section"]) == {"Summary", "Issue"}
    assert restored["Section"].tolist().count("Issue") == 2
