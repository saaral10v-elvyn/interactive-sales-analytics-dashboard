"""Tests for the reusable validation checks and report rules."""

import pandas as pd

from sales_dashboard.models import ValidationIssue, ValidationReport
from sales_dashboard.validation import (
    build_report,
    discount_issues,
    discount_scale,
    duplicate_issue,
    example_values,
    invalid_date_issue,
    invalid_numeric_issue,
    outlier_issue,
    outlier_result,
    status_mask,
)


def test_duplicate_issue_counts_only_extra_copies() -> None:
    dataframe = pd.DataFrame({"a": ["x", "x", "y"], "b": ["1", "1", "2"]})

    issue = duplicate_issue(dataframe)

    assert issue is not None
    assert issue.code == "DUPLICATE_EXACT"
    assert issue.affected_rows == 1
    assert issue.examples


def test_invalid_date_issue_ignores_blank_values() -> None:
    raw = pd.Series(["2026-01-01", "", "nope"])
    parsed = pd.to_datetime(raw, errors="coerce", format="mixed")

    issue = invalid_date_issue(raw, parsed)

    assert issue is not None
    assert issue.affected_rows == 1
    assert issue.examples == ("nope",)


def test_invalid_numeric_issue_reports_action() -> None:
    raw = pd.Series(["10", "abc", ""])
    numeric = pd.to_numeric(raw, errors="coerce")

    issue = invalid_numeric_issue(raw, numeric, "quantity")

    assert issue is not None
    assert issue.affected_rows == 1
    assert "dropped" in issue.action_taken
    assert issue.examples == ("abc",)


def test_wide_iqr_rule_finds_extreme_outlier_without_removing_it() -> None:
    series = pd.Series([1, 2, 3, 4, 5] * 5 + [1000])

    mask, lower, upper = outlier_result(series)

    assert bool(mask.iloc[-1]) is True
    assert int(mask.sum()) == 1
    assert lower is not None and upper is not None
    issue = outlier_issue(series, "revenue")
    assert issue is not None
    assert issue.severity == "warning"
    assert "Preserved" in issue.action_taken


def test_small_columns_are_not_treated_as_outliers() -> None:
    mask, lower, upper = outlier_result(pd.Series([1, 2, 1000]))

    assert not mask.any()
    assert lower is None and upper is None


def test_discount_fraction_is_detected_and_documented() -> None:
    raw = pd.Series(["0.10", "0.25", "0"])

    scale, interpretation = discount_scale(raw)
    issues = discount_issues(raw, pd.to_numeric(raw), scale, interpretation)

    assert scale == 100.0
    assert interpretation == "fraction"
    codes = {issue.code for issue in issues}
    assert "DISCOUNT_FRACTION" in codes


def test_discount_percentage_out_of_range_is_flagged() -> None:
    raw = pd.Series(["10", "150", "-5"])

    scale, interpretation = discount_scale(raw)
    issues = discount_issues(raw, pd.to_numeric(raw), scale, interpretation)

    codes = {issue.code for issue in issues}
    assert scale == 1.0
    assert "DISCOUNT_OUT_OF_RANGE" in codes


def test_status_mask_handles_spelling_variants() -> None:
    from sales_dashboard.validation import EXCLUDED_STATUSES

    mask = status_mask(
        pd.Series(["Completed", "Canceled", "voided", "Refunded"]), EXCLUDED_STATUSES
    )

    assert mask.tolist() == [False, True, True, True]


def test_report_warns_when_more_than_twenty_percent_dropped() -> None:
    report = build_report(
        [],
        rows_input=10,
        rows_output=7,
    )

    assert report.rows_dropped == 3
    assert report.should_warn_about_drops is True


def test_report_blocks_when_no_rows_remain() -> None:
    report = build_report([], rows_input=5, rows_output=0)

    assert report.blocked is True
    assert report.block_reason
    assert any(issue.code == "NO_USABLE_ROWS" for issue in report.issues)


def test_example_values_are_distinct_and_limited() -> None:
    values = pd.Series(["a", "a", "b", "c", "d", "e", "f"])

    assert example_values(values, limit=3) == ("a", "b", "c")


def test_report_severity_helpers() -> None:
    issues = [
        ValidationIssue("error", "E", "desc", 1, "action"),
        ValidationIssue("warning", "W", "desc", 2, "action"),
        ValidationIssue("info", "I", "desc", 3, "action"),
    ]
    report = ValidationReport(issues=tuple(issues), rows_input=3, rows_output=3, rows_dropped=0)

    assert report.issue_count("error") == 1
    assert len(report.warnings) == 1
    assert report.errors[0].code == "E"
