"""Reusable data-quality checks.

Every helper here is independent of Streamlit and returns a
:class:`~sales_dashboard.models.ValidationIssue` (or nothing when the check
passes). The cleaning pipeline assembles these issues into a single report.
"""

from __future__ import annotations

import pandas as pd

from sales_dashboard.models import Severity, ValidationIssue, ValidationReport

OUTLIER_IQR_MULTIPLIER = 3.0
OUTLIER_MIN_VALUES = 20

EXCLUDED_STATUSES = frozenset({"cancelled", "canceled", "refunded", "void", "voided"})
STATUS_ALIASES = {
    "canceled": "cancelled",
    "voided": "void",
    "refund": "refunded",
    "return": "returned",
}


def example_values(values: pd.Series, limit: int = 5) -> tuple[str, ...]:
    """Return up to ``limit`` distinct, readable example values."""
    text = values.dropna().astype("string").str.strip()
    text = text[text.ne("")]
    seen: list[str] = []
    for value in text:
        shown = str(value)
        if shown not in seen:
            seen.append(shown)
        if len(seen) >= limit:
            break
    return tuple(seen)


def normalize_status_text(series: pd.Series) -> pd.Series:
    """Trim, collapse whitespace and lower-case status values."""
    text = series.astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
    lowered = text.str.lower()
    mapped = lowered.replace(STATUS_ALIASES)
    return mapped.mask(text.eq(""))


def status_mask(series: pd.Series, statuses: frozenset[str]) -> pd.Series:
    """Return a boolean mask for rows whose normalised status is excluded."""
    return normalize_status_text(series).isin(statuses).fillna(False)


def duplicate_issue(dataframe: pd.DataFrame) -> ValidationIssue | None:
    """Report exact duplicate rows (beyond the first copy)."""
    mask = dataframe.duplicated(keep="first")
    count = int(mask.sum())
    if count == 0:
        return None
    examples = tuple(
        " | ".join(str(value) for value in row)
        for row in dataframe[mask].head(3).itertuples(index=False, name=None)
    )
    return ValidationIssue(
        severity="warning",
        code="DUPLICATE_EXACT",
        description=(
            "Rows that are exact copies of an earlier row. Repeated order IDs with "
            "different products are legitimate line items and are not removed."
        ),
        affected_rows=count,
        action_taken="Removed duplicate copies; the first occurrence was kept.",
        examples=examples,
    )


def missing_required_issue(
    raw: pd.Series,
    field_label: str,
) -> ValidationIssue | None:
    """Report blank values in a required column."""
    text = raw.astype("string").str.strip()
    mask = text.eq("") | text.isna()
    count = int(mask.sum())
    if count == 0:
        return None
    return ValidationIssue(
        severity="error",
        code="MISSING_REQUIRED",
        description=f"Rows with no {field_label} value.",
        affected_rows=count,
        action_taken=f"Rows were dropped because {field_label} is required for analysis.",
        examples=("(blank)",),
    )


def invalid_date_issue(
    raw: pd.Series,
    parsed: pd.Series,
    ambiguity_count: int = 0,
) -> ValidationIssue | None:
    """Report values that could not be read as dates."""
    text = raw.astype("string").str.strip()
    invalid_mask = parsed.isna() & text.ne("") & text.notna()
    count = int(invalid_mask.sum())
    if count == 0:
        return None
    examples = example_values(raw[invalid_mask])
    description = "Values that could not be read as dates."
    if ambiguity_count:
        description += f" A separate decision was needed for {ambiguity_count:,} ambiguous dates."
    return ValidationIssue(
        severity="error",
        code="DATE_INVALID",
        description=description,
        affected_rows=count,
        action_taken="Rows with unreadable dates were dropped.",
        examples=examples,
    )


def invalid_numeric_issue(
    raw: pd.Series,
    numeric: pd.Series,
    field_label: str,
    *,
    code: str = "NUMERIC_INVALID",
    severity: Severity = "error",
    description: str | None = None,
    action_taken: str | None = None,
) -> ValidationIssue | None:
    """Report non-empty values that could not be converted to numbers."""
    text = raw.astype("string").str.strip()
    invalid_mask = numeric.isna() & text.ne("") & text.notna()
    count = int(invalid_mask.sum())
    if count == 0:
        return None
    return ValidationIssue(
        severity=severity,
        code=code,
        description=description or f"Values that could not be read as {field_label} numbers.",
        affected_rows=count,
        action_taken=action_taken
        or f"Affected rows were dropped because {field_label} is required.",
        examples=example_values(raw[invalid_mask]),
    )


def outlier_result(series: pd.Series) -> tuple[pd.Series, float | None, float | None]:
    """Flag statistical outliers with a wide 3xIQR rule.

    A wide rule avoids treating normal small quantities as suspicious. The
    returned mask always preserves the rows; callers only report them.
    """
    numeric = pd.to_numeric(series, errors="coerce")
    valid = numeric.dropna()
    mask = pd.Series(False, index=numeric.index, dtype=bool)
    if len(valid) < OUTLIER_MIN_VALUES:
        return mask, None, None

    q1 = float(valid.quantile(0.25))
    q3 = float(valid.quantile(0.75))
    iqr = q3 - q1
    if iqr <= 0:
        return mask, None, None

    lower = q1 - OUTLIER_IQR_MULTIPLIER * iqr
    upper = q3 + OUTLIER_IQR_MULTIPLIER * iqr
    mask = (numeric < lower) | (numeric > upper)
    return mask.fillna(False), lower, upper


def outlier_issue(
    series: pd.Series,
    field_label: str,
    display_series: pd.Series | None = None,
) -> ValidationIssue | None:
    """Report outliers without removing them."""
    mask, lower, upper = outlier_result(series)
    count = int(mask.sum())
    if count == 0:
        return None
    shown = display_series if display_series is not None else series
    bounds = ""
    if lower is not None and upper is not None:
        bounds = f" Values outside {lower:,.2f} to {upper:,.2f} were flagged."
    return ValidationIssue(
        severity="warning",
        code="OUTLIER",
        description=f"Unusually large or small {field_label} values.{bounds}",
        affected_rows=count,
        action_taken="Preserved in the cleaned data and flagged for review.",
        examples=example_values(shown[mask]),
    )


def returns_issue(quantity: pd.Series) -> ValidationIssue | None:
    """Report negative quantities, which are treated as returns."""
    count = int((quantity < 0).sum())
    if count == 0:
        return None
    return ValidationIssue(
        severity="info",
        code="RETURNS_PRESERVED",
        description="Negative quantities interpreted as product returns.",
        affected_rows=count,
        action_taken="Kept in the dataset and netted against sales in revenue totals.",
        examples=example_values(quantity[quantity < 0].astype("string")),
    )


def zero_quantity_issue(quantity: pd.Series) -> ValidationIssue | None:
    """Report zero quantities as unusual but usable rows."""
    count = int((quantity == 0).sum())
    if count == 0:
        return None
    return ValidationIssue(
        severity="warning",
        code="ZERO_QUANTITY",
        description="Rows with a quantity of zero.",
        affected_rows=count,
        action_taken="Kept, but they contribute no units or revenue.",
        examples=("0",),
    )


def status_exclusion_issue(series: pd.Series) -> ValidationIssue | None:
    """Report cancelled, refunded or void rows excluded by default."""
    mask = status_mask(series, EXCLUDED_STATUSES)
    count = int(mask.sum())
    if count == 0:
        return None
    return ValidationIssue(
        severity="info",
        code="STATUS_EXCLUDED",
        description=(
            "Cancelled, refunded or void records. These are excluded by default "
            "because they are not completed sales."
        ),
        affected_rows=count,
        action_taken=(
            "Excluded from the cleaned dataset. Returned orders stay included as "
            "negative quantities."
        ),
        examples=example_values(series[mask]),
    )


def discount_scale(series: pd.Series) -> tuple[float, str]:
    """Return the multiplier and interpretation for discount values.

    ``0.10`` is a fraction (10%) when every value is between 0 and 1. Otherwise
    values are treated as percentages.
    """
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return 1.0, "percent"
    if numeric.min() >= 0 and numeric.max() <= 1 and (numeric > 0).any():
        return 100.0, "fraction"
    return 1.0, "percent"


def discount_issues(
    raw: pd.Series,
    numeric: pd.Series,
    scale: float,
    interpretation: str,
) -> tuple[ValidationIssue, ...]:
    """Report discount fractions and values outside the usable range."""
    issues: list[ValidationIssue] = []
    text = raw.astype("string").str.strip()
    invalid_mask = numeric.isna() & text.ne("") & text.notna()
    if invalid_mask.any():
        issues.append(
            ValidationIssue(
                severity="warning",
                code="DISCOUNT_INVALID",
                description="Discount values that could not be read as numbers.",
                affected_rows=int(invalid_mask.sum()),
                action_taken="A discount of 0 was used for these rows.",
                examples=example_values(raw[invalid_mask]),
            )
        )

    scaled = numeric * scale
    out_of_range = scaled.notna() & ((scaled < 0) | (scaled > 100))
    if out_of_range.any():
        issues.append(
            ValidationIssue(
                severity="warning",
                code="DISCOUNT_OUT_OF_RANGE",
                description="Discounts outside the expected 0–100 percentage range.",
                affected_rows=int(out_of_range.sum()),
                action_taken=(
                    "A discount of 0 was used for revenue on these rows; the original "
                    "values remain visible in the report."
                ),
                examples=example_values(raw[out_of_range]),
            )
        )

    if interpretation == "fraction" and numeric.notna().any():
        issues.append(
            ValidationIssue(
                severity="info",
                code="DISCOUNT_FRACTION",
                description=(
                    "Discounts between 0 and 1 were interpreted as fractions: "
                    "0.10 means 10%, not 0.10%."
                ),
                affected_rows=int((numeric > 0).sum()),
                action_taken="Converted to percentages before calculating revenue.",
                examples=example_values(raw[numeric > 0]),
            )
        )
    return tuple(issues)


def negative_price_issue(series: pd.Series, field_label: str) -> ValidationIssue | None:
    """Report negative prices or line totals."""
    count = int((series < 0).sum())
    if count == 0:
        return None
    return ValidationIssue(
        severity="warning",
        code="NEGATIVE_PRICE",
        description=f"Rows with a negative {field_label}.",
        affected_rows=count,
        action_taken="Kept and included in revenue; review these rows if unexpected.",
        examples=example_values(series[series < 0].astype("string")),
    )


def line_total_conflict_issue(
    conflict_mask: pd.Series,
    supplied: pd.Series,
    calculated: pd.Series,
) -> ValidationIssue | None:
    """Report rows where supplied line_total disagrees with the calculation."""
    count = int(conflict_mask.sum())
    if count == 0:
        return None
    examples = tuple(
        f"supplied {supplied_value:,.2f}, calculated {calculated_value:,.2f}"
        for supplied_value, calculated_value in zip(
            supplied[conflict_mask].head(3),
            calculated[conflict_mask].head(3),
            strict=False,
        )
    )
    return ValidationIssue(
        severity="warning",
        code="LINE_TOTAL_CONFLICT",
        description=(
            "Rows where the supplied line_total differs from quantity × unit_price after discount."
        ),
        affected_rows=count,
        action_taken=(
            "The supplied line_total was used because it may include line-level "
            "charges or adjustments."
        ),
        examples=examples,
    )


def revenue_unavailable_issue(mask: pd.Series) -> ValidationIssue | None:
    """Report rows with no usable price information."""
    count = int(mask.sum())
    if count == 0:
        return None
    return ValidationIssue(
        severity="error",
        code="REVENUE_UNAVAILABLE",
        description=("Rows where neither line_total nor unit_price could produce a revenue value."),
        affected_rows=count,
        action_taken="Rows were dropped because revenue cannot be calculated.",
        examples=("no usable price",),
    )


def text_normalization_issue(changed_rows: int) -> ValidationIssue | None:
    """Report whitespace/case normalisation applied to text fields."""
    if changed_rows <= 0:
        return None
    return ValidationIssue(
        severity="info",
        code="TEXT_NORMALIZED",
        description="Text fields with extra spaces or inconsistent capitalisation.",
        affected_rows=changed_rows,
        action_taken=(
            "Trimmed whitespace, collapsed repeated spaces and standardised category, "
            "region and status labels."
        ),
        examples=(),
    )


def order_id_missing_issue() -> ValidationIssue:
    """Explain how orders are counted when order_id is not supplied."""
    return ValidationIssue(
        severity="info",
        code="ORDER_ID_MISSING",
        description="No order_id column was provided.",
        affected_rows=0,
        action_taken=(
            "Each row is counted as one order. If your file has multiple line items "
            "per order, add an order_id column for accurate order counts."
        ),
        examples=(),
    )


def build_report(
    issues: list[ValidationIssue],
    *,
    rows_input: int,
    rows_output: int,
    date_format_used: str | None = None,
) -> ValidationReport:
    """Assemble a report and apply the no-usable-rows block rule."""
    rows_dropped = max(rows_input - rows_output, 0)
    blocked = rows_output == 0
    block_reason = None
    if blocked:
        block_reason = (
            "No usable rows remain after validation. Check the required columns "
            "and the data-quality report, then adjust the file or column mapping."
        )
        issues = [
            *issues,
            ValidationIssue(
                severity="error",
                code="NO_USABLE_ROWS",
                description="Every row failed validation or was excluded.",
                affected_rows=rows_input,
                action_taken=("Analysis is blocked until at least one valid row is available."),
                examples=(),
            ),
        ]

    return ValidationReport(
        issues=tuple(issues),
        rows_input=rows_input,
        rows_output=rows_output,
        rows_dropped=rows_dropped,
        blocked=blocked,
        block_reason=block_reason,
        date_format_used=date_format_used,
    )
