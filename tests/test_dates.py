"""Tests for date inspection and explicit DMY/MDY decisions."""

import pandas as pd
import pytest

from sales_dashboard.dates import (
    DateDecisionRequired,
    decision_label,
    inspect_dates,
    parse_dates_with_decision,
)


def test_iso_dates_need_no_decision() -> None:
    inspection = inspect_dates(pd.Series(["2026-01-15", "2026-02-20"]))

    assert inspection.total_values == 2
    assert inspection.ambiguous_count == 0
    assert not inspection.requires_decision


def test_unambiguous_day_first_dates_need_no_decision() -> None:
    inspection = inspect_dates(pd.Series(["15/04/2026", "31/12/2026"]))

    assert inspection.ambiguous_count == 0
    assert not inspection.requires_decision
    parsed = parse_dates_with_decision(pd.Series(["15/04/2026"]), "auto")
    assert parsed.iloc[0].date().isoformat() == "2026-04-15"


def test_ambiguous_dates_are_detected_with_examples() -> None:
    inspection = inspect_dates(pd.Series(["03/04/2026", "05/06/2026", "15/07/2026"]))

    assert inspection.ambiguous_count == 2
    assert inspection.requires_decision
    assert "03/04/2026" in inspection.ambiguous_examples
    assert inspection.suggested_format == "DMY"


def test_auto_mode_refuses_to_guess_ambiguous_dates() -> None:
    with pytest.raises(DateDecisionRequired) as caught:
        parse_dates_with_decision(pd.Series(["03/04/2026"]), "auto")

    assert caught.value.inspection.ambiguous_count == 1


def test_dmy_and_mdy_produce_different_dates() -> None:
    series = pd.Series(["03/04/2026"])

    dmy = parse_dates_with_decision(series, "DMY")
    mdy = parse_dates_with_decision(series, "MDY")

    assert dmy.iloc[0].date().isoformat() == "2026-04-03"
    assert mdy.iloc[0].date().isoformat() == "2026-03-04"


def test_invalid_dates_are_counted_not_silently_parsed() -> None:
    inspection = inspect_dates(pd.Series(["2026-01-15", "not-a-date", ""]))

    assert inspection.total_values == 2
    assert inspection.parseable_count == 1
    assert inspection.invalid_count == 1


def test_decision_labels_are_friendly() -> None:
    assert decision_label("DMY") == "Day first (DMY)"
    assert decision_label("MDY") == "Month first (MDY)"
    assert decision_label(None) == "Not decided"
