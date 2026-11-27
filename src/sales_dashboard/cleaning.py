"""Reusable Pandas cleaning functions for uploaded sales data.

Discount interpretation used throughout this module:

* ``discount_percent`` is a percentage of the line subtotal (0–100).
* If every supplied discount is between 0 and 1 (and at least one is above 0),
  the values are treated as fractions, so ``0.10`` becomes 10%.
* When ``line_total`` is supplied it is treated as already net of discount and
  used as the revenue value. Otherwise revenue is
  ``quantity × unit_price × (1 − discount_percent / 100)``.
* Negative quantities are returns: they stay in the dataset and reduce revenue.

Every step is a plain function or a clearly ordered pipeline so it can be tested
without the API or the browser.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from sales_dashboard.dates import (
    DateInspection,
    inspect_dates,
    parse_dates_with_decision,
)
from sales_dashboard.models import (
    CleanedDataset,
    ColumnMapping,
    DateFormatDecision,
    ValidationIssue,
)
from sales_dashboard.parsing import to_numeric
from sales_dashboard.validation import (
    EXCLUDED_STATUSES,
    build_report,
    discount_issues,
    discount_scale,
    duplicate_issue,
    invalid_date_issue,
    invalid_numeric_issue,
    line_total_conflict_issue,
    missing_required_issue,
    negative_price_issue,
    order_id_missing_issue,
    outlier_issue,
    returns_issue,
    revenue_unavailable_issue,
    status_exclusion_issue,
    status_mask,
    text_normalization_issue,
    zero_quantity_issue,
)


class CleaningError(ValueError):
    """Raised when a dataset cannot be cleaned with the current mapping."""


@dataclass(frozen=True)
class CleaningOptions:
    """User choices that affect the cleaning pipeline."""

    date_format: DateFormatDecision = "auto"
    exclude_statuses: bool = True


def _blank_mask(series: pd.Series) -> pd.Series:
    text = series.astype("string").str.strip()
    return text.eq("") | text.isna()


def _clean_whitespace(series: pd.Series) -> pd.Series:
    text = series.astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
    return text.mask(text.eq(""))


def _canonicalize_labels(series: pd.Series) -> pd.Series:
    """Merge case-only variants while keeping the most common spelling."""
    text = _clean_whitespace(series)
    folded = text.str.casefold()
    result = text.copy()
    for _, group in text[folded.notna()].groupby(folded[folded.notna()]):
        counts = group.value_counts()
        if counts.empty:
            continue
        winner = counts.index[0]
        result.loc[group.index] = winner
    return result


def _mapped_series(
    dataframe: pd.DataFrame,
    mapping: ColumnMapping,
    field: str,
) -> pd.Series | None:
    source = mapping.source_for(field)
    if source is None or source not in dataframe.columns:
        return None
    return dataframe[source]


def _numeric_or_empty(
    dataframe: pd.DataFrame,
    mapping: ColumnMapping,
    field: str,
) -> pd.Series:
    series = _mapped_series(dataframe, mapping, field)
    if series is None:
        return pd.Series(float("nan"), index=dataframe.index)
    return to_numeric(series)


def inspect_date_column(
    dataframe: pd.DataFrame,
    mapping: ColumnMapping,
) -> DateInspection | None:
    """Inspect the mapped order_date column for the preparation UI."""
    series = _mapped_series(dataframe, mapping, "order_date")
    if series is None:
        return None
    return inspect_dates(series)


def _normalize_text_columns(
    dataframe: pd.DataFrame,
    mapping: ColumnMapping,
) -> int:
    """Normalise mapped text columns in place and return changed row count."""
    changed_rows = 0
    for field in ("product", "category", "region", "status"):
        source = mapping.source_for(field)
        if source is None or source not in dataframe.columns:
            continue
        original = dataframe[source].astype("string")
        if field == "product":
            normalized = _clean_whitespace(original)
        else:
            normalized = _canonicalize_labels(original)
        changed_rows += int((original.fillna("") != normalized.fillna("")).sum())
        dataframe[source] = normalized
    return changed_rows


def _quantity_output(series: pd.Series) -> pd.Series:
    valid = series.dropna()
    if not valid.empty and (valid % 1 == 0).all():
        return series.astype("Int64")
    return series.astype("Float64")


def clean_dataset(
    raw_dataframe: pd.DataFrame,
    mapping: ColumnMapping,
    options: CleaningOptions | None = None,
    *,
    source_filename: str = "",
) -> CleanedDataset:
    """Validate and clean a raw string DataFrame.

    Raises :class:`CleaningError` when required columns are missing and
    :class:`~sales_dashboard.dates.DateDecisionRequired` when ambiguous dates
    need a DMY/MDY decision.
    """
    options = options or CleaningOptions()

    for field, source in mapping.fields.items():
        if source not in raw_dataframe.columns:
            raise CleaningError(
                f"The mapping for {field!r} points to a column that is not in this file."
            )
    if mapping.missing_required:
        missing = ", ".join(mapping.missing_required)
        raise CleaningError(
            f"Required columns are missing: {missing}. "
            "Choose the correct source columns before cleaning."
        )

    dataframe = raw_dataframe.copy()
    dataframe.columns = [str(column).strip() for column in dataframe.columns]
    dataframe = dataframe.reset_index(drop=True)
    rows_input = len(dataframe)
    issues: list[ValidationIssue] = []

    changed_rows = _normalize_text_columns(dataframe, mapping)
    issue = text_normalization_issue(changed_rows)
    if issue is not None:
        issues.append(issue)

    order_id_source = mapping.source_for("order_id")
    order_id_available = (
        order_id_source is not None and not _blank_mask(dataframe[order_id_source]).all()
    )
    if not order_id_available:
        issues.append(order_id_missing_issue())

    issue = duplicate_issue(dataframe)
    if issue is not None:
        issues.append(issue)
    dataframe = dataframe.loc[~dataframe.duplicated(keep="first")].reset_index(drop=True)

    status_source = mapping.source_for("status")
    if options.exclude_statuses and status_source is not None:
        issue = status_exclusion_issue(dataframe[status_source])
        if issue is not None:
            issues.append(issue)
        excluded = status_mask(dataframe[status_source], EXCLUDED_STATUSES)
        dataframe = dataframe.loc[~excluded].reset_index(drop=True)

    date_source = mapping.source_for("order_date")
    assert date_source is not None  # guaranteed by required-field validation
    date_raw = dataframe[date_source].astype("string")
    inspection = inspect_dates(date_raw)
    parsed_dates = parse_dates_with_decision(
        date_raw,
        options.date_format,
        inspection=inspection,
    )
    date_blank = _blank_mask(date_raw)

    issue = missing_required_issue(date_raw, "order_date")
    if issue is not None:
        issues.append(issue)
    issue = invalid_date_issue(
        date_raw,
        parsed_dates,
        ambiguity_count=inspection.ambiguous_count if options.date_format != "auto" else 0,
    )
    if issue is not None:
        issues.append(issue)
    critical = date_blank | parsed_dates.isna()

    product_source = mapping.source_for("product")
    assert product_source is not None
    product_raw = dataframe[product_source].astype("string")
    product_blank = _blank_mask(product_raw)
    issue = missing_required_issue(product_raw, "product")
    if issue is not None:
        issues.append(issue)
    critical |= product_blank

    quantity_source = mapping.source_for("quantity")
    assert quantity_source is not None
    quantity_raw = dataframe[quantity_source].astype("string")
    quantity = to_numeric(quantity_raw)
    issue = missing_required_issue(quantity_raw, "quantity")
    if issue is not None:
        issues.append(issue)
    issue = invalid_numeric_issue(quantity_raw, quantity, "quantity")
    if issue is not None:
        issues.append(issue)
    critical |= quantity.isna()

    line_total_raw = _mapped_series(dataframe, mapping, "line_total")
    unit_price_raw = _mapped_series(dataframe, mapping, "unit_price")
    discount_raw = _mapped_series(dataframe, mapping, "discount_percent")

    line_total = _numeric_or_empty(dataframe, mapping, "line_total")
    unit_price = _numeric_or_empty(dataframe, mapping, "unit_price")
    discount_numeric = _numeric_or_empty(dataframe, mapping, "discount_percent")

    if line_total_raw is not None:
        issue = invalid_numeric_issue(
            line_total_raw,
            line_total,
            "line_total",
            code="NUMERIC_INVALID_LINE_TOTAL",
            severity="warning",
            action_taken=(
                "Fell back to quantity × unit_price after discount where possible; "
                "otherwise the row was dropped."
            ),
        )
        if issue is not None:
            issues.append(issue)
    if unit_price_raw is not None:
        issue = invalid_numeric_issue(
            unit_price_raw,
            unit_price,
            "unit_price",
            code="NUMERIC_INVALID_UNIT_PRICE",
            severity="warning",
            action_taken=(
                "Used the supplied line_total where available; otherwise the row was dropped."
            ),
        )
        if issue is not None:
            issues.append(issue)

    scale, interpretation = (
        discount_scale(discount_raw) if discount_raw is not None else (1.0, "percent")
    )
    if discount_raw is not None:
        issues.extend(discount_issues(discount_raw, discount_numeric, scale, interpretation))
        discount_percent = (discount_numeric * scale).where(
            (discount_numeric * scale).between(0, 100), 0
        )
        discount_percent = discount_percent.fillna(0)
    else:
        discount_percent = pd.Series(0.0, index=dataframe.index)

    computed_revenue = quantity * unit_price * (1 - discount_percent / 100)
    revenue = line_total.where(line_total.notna(), computed_revenue)

    if line_total_raw is not None and unit_price_raw is not None:
        tolerance = line_total.abs().mul(0.01).clip(lower=0.01)
        conflict = (
            line_total.notna()
            & computed_revenue.notna()
            & ((line_total - computed_revenue).abs() > tolerance)
        )
        issue = line_total_conflict_issue(conflict, line_total, computed_revenue)
        if issue is not None:
            issues.append(issue)

    issue = revenue_unavailable_issue(revenue.isna())
    if issue is not None:
        issues.append(issue)
    critical |= revenue.isna()

    issue = negative_price_issue(unit_price, "unit_price")
    if issue is not None:
        issues.append(issue)
    # A negative line_total is expected for a return (negative quantity), so only
    # flag it when the quantity is not negative.
    issue = negative_price_issue(line_total.where(quantity >= 0), "line_total")
    if issue is not None:
        issues.append(issue)

    kept = ~critical
    cleaned = dataframe.loc[kept].reset_index(drop=True)
    parsed_dates = parsed_dates.loc[kept].reset_index(drop=True)
    quantity = quantity.loc[kept].reset_index(drop=True)
    unit_price = unit_price.loc[kept].reset_index(drop=True)
    line_total = line_total.loc[kept].reset_index(drop=True)
    discount_percent = discount_percent.loc[kept].reset_index(drop=True)
    revenue = revenue.loc[kept].reset_index(drop=True)

    issue = returns_issue(quantity)
    if issue is not None:
        issues.append(issue)
    issue = zero_quantity_issue(quantity)
    if issue is not None:
        issues.append(issue)
    # Returns are already reported separately; flag unusually large sales only.
    issue = outlier_issue(quantity.where(quantity >= 0).astype("float64"), "quantity")
    if issue is not None:
        issues.append(issue)
    issue = outlier_issue(revenue.astype("float64"), "revenue")
    if issue is not None:
        issues.append(issue)

    if discount_raw is not None:
        issues.append(
            ValidationIssue(
                severity="info",
                code="DISCOUNT_INTERPRETATION",
                description=(
                    "Discounts are percentages of the line subtotal. A supplied "
                    "line_total is treated as already net of discount; otherwise "
                    "revenue = quantity × unit_price × (1 − discount / 100)."
                ),
                affected_rows=int((discount_percent > 0).sum()),
                action_taken="Applied consistently to every cleaned row.",
                examples=(),
            )
        )

    out = pd.DataFrame(index=cleaned.index)
    if order_id_source is not None:
        out["order_id"] = cleaned[order_id_source].astype("string")
    if isinstance(parsed_dates.dtype, pd.DatetimeTZDtype):
        parsed_dates = parsed_dates.dt.tz_localize(None)
    out["order_date"] = parsed_dates.astype("datetime64[ns]")
    out["product"] = cleaned[product_source].astype("string")
    for field in ("category", "region"):
        source = mapping.source_for(field)
        if source is not None:
            out[field] = cleaned[source].astype("string")
    out["quantity"] = _quantity_output(quantity)
    out["unit_price"] = unit_price.astype("Float64")
    out["line_total"] = line_total.astype("Float64")
    out["discount_percent"] = discount_percent.astype("Float64")
    out["revenue"] = revenue.astype("Float64")
    if status_source is not None:
        out["status"] = cleaned[status_source].astype("string")
    customer_source = mapping.source_for("customer_id")
    if customer_source is not None:
        out["customer_id"] = cleaned[customer_source].astype("string")

    supplied_used = int(line_total.notna().sum())
    calculated_used = int(
        (revenue.notna() & line_total.isna() & computed_revenue.loc[kept].notna()).sum()
    )
    if supplied_used and calculated_used:
        revenue_source = "mixed (supplied line_total and calculated values)"
    elif supplied_used:
        revenue_source = "supplied line_total"
    elif calculated_used:
        revenue_source = "quantity × unit_price after discount"
    else:
        revenue_source = "not available"

    date_format_used = options.date_format if options.date_format in ("DMY", "MDY") else "auto"
    report = build_report(
        issues,
        rows_input=rows_input,
        rows_output=len(out),
        date_format_used=date_format_used,
    )

    return CleanedDataset(
        dataframe=out,
        mapping=mapping,
        report=report,
        source_filename=source_filename,
        date_format_used=date_format_used,
        revenue_source=revenue_source,
        order_id_available=order_id_available,
    )
