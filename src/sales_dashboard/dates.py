"""Date inspection and explicit DMY/MDY decisions.

Dates such as ``03/04/2026`` mean 3 April in day-first files and 4 March in
month-first files. The application must not guess: :func:`inspect_dates`
detects the ambiguity and :func:`parse_dates_with_decision` refuses to parse
until the user (or caller) supplies a decision.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

from sales_dashboard.models import DateFormatDecision

_NUMERIC_DATE = re.compile(r"^\s*(\d{1,4})[./-](\d{1,2})[./-](\d{1,4})(?:[ T].*)?$")


class DateDecisionRequired(ValueError):
    """Raised when a date column contains ambiguous day/month values."""

    def __init__(self, inspection: DateInspection) -> None:
        self.inspection = inspection
        examples = ", ".join(inspection.ambiguous_examples) or "several values"
        super().__init__(
            "The date column contains ambiguous dates "
            f"({inspection.ambiguous_count:,} rows, for example {examples}). "
            "Choose whether dates are day-first (DMY) or month-first (MDY) before cleaning."
        )


@dataclass(frozen=True)
class DateInspection:
    """What a date column looks like before a format decision is made."""

    total_values: int
    parseable_count: int
    invalid_count: int
    ambiguous_count: int
    ambiguous_examples: tuple[str, ...] = ()
    day_first_hint_count: int = 0
    month_first_hint_count: int = 0
    suggested_format: str | None = None

    @property
    def requires_decision(self) -> bool:
        """Return True when day-first and month-first readings disagree."""
        return self.ambiguous_count > 0

    @property
    def valid_ratio(self) -> float:
        """Return the share of non-empty values that look like dates."""
        if self.total_values <= 0:
            return 0.0
        return self.parseable_count / self.total_values


def _clean_text(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip()


def _parse(series: pd.Series, *, dayfirst: bool) -> pd.Series:
    if series.empty:
        return pd.Series([], dtype="datetime64[ns]")
    return pd.to_datetime(series, errors="coerce", format="mixed", dayfirst=dayfirst)


def _numeric_parts(value: str) -> tuple[int, int] | None:
    """Return the first two numeric components of a numeric date string."""
    match = _NUMERIC_DATE.match(value)
    if not match:
        return None
    first, second = match.group(1), match.group(2)
    try:
        return int(first), int(second)
    except ValueError:
        return None


def inspect_dates(series: pd.Series) -> DateInspection:
    """Inspect a date column for ambiguity without choosing a format."""
    text = _clean_text(series)
    non_empty = text[text.ne("") & text.notna()]
    total_values = int(len(non_empty))
    if total_values == 0:
        return DateInspection(
            total_values=0,
            parseable_count=0,
            invalid_count=0,
            ambiguous_count=0,
        )

    day_first = _parse(non_empty, dayfirst=True)
    month_first = _parse(non_empty, dayfirst=False)

    day_valid = day_first.notna()
    month_valid = month_first.notna()
    both_valid = day_valid & month_valid

    # Values where both readings work but produce a different calendar day.
    different = both_valid & (
        day_first.dt.normalize().to_numpy() != month_first.dt.normalize().to_numpy()
    )
    ambiguous_mask = pd.Series(different, index=non_empty.index, dtype=bool)

    ambiguous_values = non_empty[ambiguous_mask].drop_duplicates()
    examples = tuple(str(value) for value in ambiguous_values.head(5))

    day_hints = 0
    month_hints = 0
    for value in non_empty[day_valid | month_valid].head(5_000):
        parts = _numeric_parts(str(value))
        if parts is None:
            continue
        first, second = parts
        if first > 12:
            day_hints += 1
        elif second > 12:
            month_hints += 1

    suggested: str | None = None
    if ambiguous_mask.any():
        if day_hints > month_hints:
            suggested = "DMY"
        elif month_hints > day_hints:
            suggested = "MDY"

    parseable = int((day_valid | month_valid).sum())
    return DateInspection(
        total_values=total_values,
        parseable_count=parseable,
        invalid_count=total_values - parseable,
        ambiguous_count=int(ambiguous_mask.sum()),
        ambiguous_examples=examples,
        day_first_hint_count=day_hints,
        month_first_hint_count=month_hints,
        suggested_format=suggested,
    )


def parse_dates_with_decision(
    series: pd.Series,
    decision: DateFormatDecision = "auto",
    *,
    inspection: DateInspection | None = None,
) -> pd.Series:
    """Parse a date column using an explicit day-first or month-first choice.

    ``auto`` is only allowed when no ambiguous values exist. It still parses
    unambiguous day-first values such as ``15/04/2026`` correctly. Pass an
    existing ``inspection`` to avoid inspecting the same column twice.
    """
    text = _clean_text(series)
    normalized = decision.upper() if decision else "AUTO"

    if normalized == "AUTO":
        inspection = inspection or inspect_dates(series)
        if inspection.requires_decision:
            raise DateDecisionRequired(inspection)
        dayfirst = False
    elif normalized == "DMY":
        dayfirst = True
    elif normalized == "MDY":
        dayfirst = False
    else:
        raise ValueError(f"Unsupported date decision: {decision!r}")

    if text.empty:
        return pd.Series([], dtype="datetime64[ns]")
    return pd.to_datetime(text, errors="coerce", format="mixed", dayfirst=dayfirst)


def decision_label(decision: str | None) -> str:
    """Return a friendly label for a date-format decision."""
    labels = {
        "DMY": "Day first (DMY)",
        "MDY": "Month first (MDY)",
        "auto": "Automatic (unambiguous dates only)",
    }
    return labels.get(decision or "", "Not decided")
