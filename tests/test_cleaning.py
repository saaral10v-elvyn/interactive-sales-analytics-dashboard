"""Tests for the reusable cleaning pipeline."""

import pandas as pd
import pytest

from sales_dashboard.cleaning import (
    CleaningError,
    CleaningOptions,
    clean_dataset,
    inspect_date_column,
)
from sales_dashboard.dates import DateDecisionRequired
from sales_dashboard.schema import detect_dataframe_mapping


def _clean(
    dataframe: pd.DataFrame,
    *,
    options: CleaningOptions | None = None,
):
    mapping = detect_dataframe_mapping(dataframe)
    return clean_dataset(
        dataframe,
        mapping,
        options or CleaningOptions(),
        source_filename="test.csv",
    )


def _basic(**overrides) -> pd.DataFrame:
    data = {
        "order_id": ["A", "A"],
        "order_date": ["2026-01-01", "2026-01-02"],
        "product": ["Pen", "Pad"],
        "quantity": ["1", "2"],
        "unit_price": ["10", "20"],
    }
    data.update(overrides)
    return pd.DataFrame(data)


def test_computes_revenue_when_only_unit_price_is_available() -> None:
    result = _clean(_basic())

    assert result.report.rows_output == 2
    assert result.dataframe["revenue"].tolist() == [10.0, 40.0]
    assert result.revenue_source == "quantity × unit_price after discount"
    assert "line_total" in result.dataframe.columns


def test_supplied_line_total_wins_and_conflict_is_reported() -> None:
    dataframe = pd.DataFrame(
        {
            "order_date": ["2026-01-01", "2026-01-02"],
            "product": ["Pen", "Pad"],
            "quantity": ["2", "2"],
            "unit_price": ["10", "10"],
            "discount_percent": ["0", "10"],
            "line_total": ["25", ""],
        }
    )

    result = _clean(dataframe)

    assert result.dataframe["revenue"].tolist() == [25.0, 18.0]
    assert result.revenue_source.startswith("mixed")
    codes = {issue.code for issue in result.report.issues}
    assert "LINE_TOTAL_CONFLICT" in codes


def test_only_line_total_is_supported() -> None:
    dataframe = pd.DataFrame(
        {
            "order_date": ["2026-01-01"],
            "product": ["Pen"],
            "quantity": ["2"],
            "line_total": ["18"],
        }
    )

    result = _clean(dataframe)

    assert result.dataframe["revenue"].tolist() == [18.0]
    assert result.revenue_source == "supplied line_total"


def test_exact_duplicates_are_removed_but_line_items_are_kept() -> None:
    dataframe = pd.DataFrame(
        {
            "order_id": ["A", "A", "A", "B"],
            "order_date": ["2026-01-01"] * 4,
            "product": ["Pen", "Pen", "Pad", "Pen"],
            "quantity": ["1", "1", "1", "1"],
            "unit_price": ["10", "10", "10", "10"],
        }
    )

    result = _clean(dataframe)

    assert result.report.rows_input == 4
    assert result.report.rows_output == 3
    assert result.dataframe["product"].tolist() == ["Pen", "Pad", "Pen"]
    issue = next(issue for issue in result.report.issues if issue.code == "DUPLICATE_EXACT")
    assert issue.affected_rows == 1


def test_ambiguous_dates_require_a_decision() -> None:
    dataframe = pd.DataFrame(
        {
            "order_date": ["03/04/2026", "05/06/2026"],
            "product": ["Pen", "Pad"],
            "quantity": ["1", "1"],
            "unit_price": ["10", "10"],
        }
    )

    with pytest.raises(DateDecisionRequired):
        _clean(dataframe)

    dmy = _clean(dataframe, options=CleaningOptions(date_format="DMY"))
    mdy = _clean(dataframe, options=CleaningOptions(date_format="MDY"))

    assert dmy.dataframe["order_date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2026-04-03",
        "2026-06-05",
    ]
    assert mdy.dataframe["order_date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2026-03-04",
        "2026-05-06",
    ]


def test_inspect_date_column_uses_the_mapping() -> None:
    dataframe = pd.DataFrame(
        {
            "Date": ["03/04/2026", "15/05/2026"],
            "Item": ["Pen", "Pad"],
            "Qty": ["1", "1"],
            "Price": ["10", "10"],
        }
    )
    mapping = detect_dataframe_mapping(dataframe)

    inspection = inspect_date_column(dataframe, mapping)

    assert inspection is not None
    assert inspection.ambiguous_count == 1


def test_returns_are_preserved_and_netted() -> None:
    dataframe = pd.DataFrame(
        {
            "order_id": ["A", "B"],
            "order_date": ["2026-01-01", "2026-01-02"],
            "product": ["Pen", "Pen"],
            "quantity": ["2", "-1"],
            "unit_price": ["10", "10"],
            "status": ["Completed", "Returned"],
        }
    )

    result = _clean(dataframe)

    assert result.report.rows_output == 2
    assert result.dataframe["quantity"].tolist() == [2, -1]
    assert result.dataframe["revenue"].tolist() == [20.0, -10.0]
    assert result.dataframe["revenue"].sum() == 10.0
    codes = {issue.code for issue in result.report.issues}
    assert "RETURNS_PRESERVED" in codes


def test_cancelled_refunded_and_void_are_excluded_by_default() -> None:
    dataframe = pd.DataFrame(
        {
            "order_id": ["A", "B", "C", "D", "E"],
            "order_date": ["2026-01-01"] * 5,
            "product": ["Pen"] * 5,
            "quantity": ["1", "1", "1", "1", "-1"],
            "unit_price": ["10"] * 5,
            "status": ["Completed", "Cancelled", "Refunded", "Void", "Returned"],
        }
    )

    excluded = _clean(dataframe)
    kept = _clean(dataframe, options=CleaningOptions(exclude_statuses=False))

    assert excluded.report.rows_output == 2
    assert excluded.dataframe["status"].tolist() == ["Completed", "Returned"]
    assert kept.report.rows_output == 5
    issue = next(issue for issue in excluded.report.issues if issue.code == "STATUS_EXCLUDED")
    assert issue.affected_rows == 3


def test_missing_order_id_counts_each_row_as_one_order() -> None:
    dataframe = pd.DataFrame(
        {
            "order_date": ["2026-01-01", "2026-01-02"],
            "product": ["Pen", "Pad"],
            "quantity": ["1", "2"],
            "unit_price": ["10", "20"],
        }
    )

    result = _clean(dataframe)

    assert result.order_id_available is False
    assert "order_id" not in result.dataframe.columns
    issue = next(issue for issue in result.report.issues if issue.code == "ORDER_ID_MISSING")
    assert "one order" in issue.action_taken


def test_text_and_category_values_are_normalised() -> None:
    dataframe = pd.DataFrame(
        {
            "order_date": ["2026-01-01", "2026-01-01", "2026-01-02", "2026-01-03"],
            "product": ["  Pen  ", "Pad", "Pen", "Pen"],
            "category": ["electronics", "Electronics", "ELECTRONICS", "Home"],
            "quantity": ["1"] * 4,
            "unit_price": ["10"] * 4,
        }
    )

    result = _clean(dataframe)

    assert result.dataframe["product"].tolist() == ["Pen", "Pad", "Pen", "Pen"]
    assert result.dataframe["category"].nunique() == 2
    assert "Home" in result.dataframe["category"].tolist()
    codes = {issue.code for issue in result.report.issues}
    assert "TEXT_NORMALIZED" in codes


def test_invalid_required_values_are_dropped_with_a_report() -> None:
    dataframe = pd.DataFrame(
        {
            "order_date": ["2026-01-01", "not-a-date", "2026-01-03", "2026-01-04", "2026-01-05"],
            "product": ["Pen", "Pad", "", "Pen", "Pad"],
            "quantity": ["1", "1", "1", "abc", "2"],
            "unit_price": ["10"] * 5,
        }
    )

    result = _clean(dataframe)

    assert result.report.rows_input == 5
    assert result.report.rows_output == 2
    assert result.report.rows_dropped == 3
    assert result.report.should_warn_about_drops is True
    codes = {issue.code for issue in result.report.issues}
    assert {"DATE_INVALID", "MISSING_REQUIRED", "NUMERIC_INVALID"} <= codes


def test_no_usable_rows_blocks_analysis() -> None:
    dataframe = pd.DataFrame(
        {
            "order_date": ["bad", "worse"],
            "product": ["Pen", "Pad"],
            "quantity": ["1", "2"],
            "unit_price": ["10", "20"],
        }
    )

    result = _clean(dataframe)

    assert result.report.rows_output == 0
    assert result.report.blocked is True
    assert result.report.block_reason
    assert any(issue.code == "NO_USABLE_ROWS" for issue in result.report.issues)


def test_outliers_are_preserved_and_flagged() -> None:
    quantities = [str(value) for value in range(1, 25)] + ["10000"]
    dataframe = pd.DataFrame(
        {
            "order_date": ["2026-01-01"] * 25,
            "product": ["Pen"] * 25,
            "quantity": quantities,
            "unit_price": ["10"] * 25,
        }
    )

    result = _clean(dataframe)

    assert result.report.rows_output == 25
    outlier_issues = [issue for issue in result.report.issues if issue.code == "OUTLIER"]
    assert outlier_issues
    assert all("Preserved" in issue.action_taken for issue in outlier_issues)


def test_discount_fraction_is_converted_to_percentage() -> None:
    dataframe = pd.DataFrame(
        {
            "order_date": ["2026-01-01"],
            "product": ["Pen"],
            "quantity": ["2"],
            "unit_price": ["10"],
            "discount": ["0.10"],
        }
    )

    result = _clean(dataframe)

    assert result.dataframe["discount_percent"].tolist() == [10.0]
    assert result.dataframe["revenue"].tolist() == [18.0]
    assert any(issue.code == "DISCOUNT_FRACTION" for issue in result.report.issues)


def test_out_of_range_discount_uses_zero_and_is_reported() -> None:
    dataframe = pd.DataFrame(
        {
            "order_date": ["2026-01-01"],
            "product": ["Pen"],
            "quantity": ["2"],
            "unit_price": ["10"],
            "discount_percent": ["150"],
        }
    )

    result = _clean(dataframe)

    assert result.dataframe["discount_percent"].tolist() == [0.0]
    assert result.dataframe["revenue"].tolist() == [20.0]
    assert any(issue.code == "DISCOUNT_OUT_OF_RANGE" for issue in result.report.issues)


def test_missing_required_mapping_raises_a_clear_error() -> None:
    dataframe = pd.DataFrame({"product": ["Pen"], "quantity": ["1"], "unit_price": ["10"]})
    mapping = detect_dataframe_mapping(dataframe)

    with pytest.raises(CleaningError, match="Required columns are missing"):
        clean_dataset(dataframe, mapping)


def test_cleaned_columns_are_canonical_and_typed() -> None:
    result = _clean(
        _basic(
            order_id=["A", "B"],
            category=["Office", "Office"],
            region=["North", "South"],
            status=["Completed", "Completed"],
            customer_id=["C1", "C2"],
        )
    )

    assert list(result.dataframe.columns) == [
        "order_id",
        "order_date",
        "product",
        "category",
        "region",
        "quantity",
        "unit_price",
        "line_total",
        "discount_percent",
        "revenue",
        "status",
        "customer_id",
    ]
    assert str(result.dataframe["order_date"].dtype) == "datetime64[ns]"
    assert str(result.dataframe["quantity"].dtype) == "Int64"
