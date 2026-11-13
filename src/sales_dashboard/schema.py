"""Canonical sales schema, alias detection and confidence scoring.

Detection runs in three passes:

1. Exact alias matches on normalised headers (confidence 1.0).
2. Fuzzy header matches for small spelling differences (confidence ~0.8).
3. Conservative content checks for dates, statuses and a single text column.

Anything uncertain is marked as low confidence so the Home page can ask the
user to confirm or override it before cleaning.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher

import pandas as pd

from sales_dashboard.dates import inspect_dates
from sales_dashboard.models import ColumnMapping

# Canonical field -> accepted aliases. Both sides are normalised before matching.
FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "order_id": (
        "order_id",
        "orderid",
        "order_number",
        "order_no",
        "order_code",
        "order_ref",
        "invoice_id",
        "invoice_number",
        "invoice_no",
        "bill_no",
        "transaction_id",
        "reference",
    ),
    "order_date": (
        "order_date",
        "order_dt",
        "date",
        "purchase_date",
        "sales_date",
        "invoice_date",
        "transaction_date",
        "date_of_order",
        "created_at",
        "order_datetime",
    ),
    "customer_id": (
        "customer_id",
        "customerid",
        "customer",
        "customer_code",
        "client_id",
        "client",
    ),
    "product": (
        "product",
        "product_name",
        "product_title",
        "product_description",
        "item",
        "item_name",
        "item_description",
        "description",
        "sku_name",
        "goods",
    ),
    "category": (
        "category",
        "product_category",
        "product_type",
        "department",
        "segment",
    ),
    "region": (
        "region",
        "sales_region",
        "territory",
        "state",
        "zone",
        "area",
        "location",
        "city",
    ),
    "quantity": (
        "quantity",
        "qty",
        "qty_ordered",
        "order_qty",
        "units",
        "units_sold",
        "quantity_sold",
        "units_purchased",
        "num_units",
        "count",
    ),
    "unit_price": (
        "unit_price",
        "unitprice",
        "unit_cost",
        "price",
        "rate",
        "mrp",
        "list_price",
        "selling_price",
        "price_per_unit",
        "price_per_item",
        "item_price",
    ),
    "line_total": (
        "line_total",
        "linetotal",
        "total",
        "order_total",
        "invoice_total",
        "revenue",
        "sales",
        "amount",
        "total_amount",
        "line_amount",
        "sales_amount",
        "gross_sales",
        "gross_amount",
        "net_sales",
    ),
    "discount_percent": (
        "discount_percent",
        "discount_percentage",
        "discount_pct",
        "discount_rate",
        "discount",
        "disc",
        "discount_value",
    ),
    "status": (
        "status",
        "order_status",
        "order_state",
        "transaction_status",
    ),
}

REQUIRED_FIELDS = ("order_date", "product", "quantity")
PRICE_FIELDS = ("unit_price", "line_total")

FIELD_LABELS: dict[str, str] = {
    "order_id": "order_id",
    "order_date": "order_date",
    "customer_id": "customer_id",
    "product": "product",
    "category": "category",
    "region": "region",
    "quantity": "quantity",
    "unit_price": "unit_price",
    "line_total": "line_total",
    "discount_percent": "discount_percent",
    "status": "status",
}

FIELD_ORDER = tuple(FIELD_LABELS)

# Content-only matches are deliberately conservative: the user is asked to
# confirm anything below this threshold.
LOW_CONFIDENCE_THRESHOLD = 0.75
_FUZZY_THRESHOLD = 0.88
_STATUS_WORDS = {
    "completed",
    "complete",
    "cancelled",
    "canceled",
    "refunded",
    "refund",
    "void",
    "voided",
    "returned",
    "return",
    "pending",
    "processing",
    "shipped",
    "delivered",
}


@dataclass(frozen=True)
class FieldGuide:
    """A row in the Home page's CSV format guide."""

    column: str
    requirement: str
    description: str
    example: str


FIELD_GUIDE: tuple[FieldGuide, ...] = (
    FieldGuide(
        "order_id",
        "Recommended",
        "Unique order identifier. Used to count distinct orders.",
        "ORD-00001",
    ),
    FieldGuide(
        "order_date",
        "Required",
        "Date of the sale. ISO format is recommended.",
        "2026-01-15",
    ),
    FieldGuide(
        "product",
        "Required",
        "Product or item name.",
        "Wireless Headphones",
    ),
    FieldGuide(
        "quantity",
        "Required",
        "Units sold. Negative values are treated as returns.",
        "2",
    ),
    FieldGuide(
        "unit_price",
        "Required*",
        "Price per unit. Provide this or line_total.",
        "2499",
    ),
    FieldGuide(
        "line_total",
        "Required*",
        "Net amount for the line. Provide this or unit_price.",
        "4498.20",
    ),
    FieldGuide(
        "category",
        "Optional",
        "Product category.",
        "Electronics",
    ),
    FieldGuide(
        "region",
        "Optional",
        "Sales region or territory.",
        "North",
    ),
    FieldGuide(
        "discount_percent",
        "Optional",
        "Discount applied, from 0 to 100.",
        "10",
    ),
    FieldGuide(
        "status",
        "Optional",
        "Order status such as Completed, Cancelled or Returned.",
        "Completed",
    ),
    FieldGuide(
        "customer_id",
        "Optional",
        "Customer identifier.",
        "CUST-0042",
    ),
)


class MappingError(ValueError):
    """Raised when a manual column mapping is invalid."""


def normalize_column_name(name: str) -> str:
    """Normalise a header for alias comparison.

    Example: ``"Order Date"`` becomes ``"order_date"`` and ``"Qty."`` becomes
    ``"qty"``.
    """
    cleaned = re.sub(r"[^0-9a-zA-Z]+", "_", str(name).strip().lower())
    return cleaned.strip("_")


def _normalized_lookup(columns: Sequence[str]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for source in columns:
        normalized = normalize_column_name(source)
        if normalized and normalized not in lookup:
            lookup[normalized] = source
    return lookup


def _add_match(
    fields: dict[str, str],
    confidence: dict[str, float],
    methods: dict[str, str],
    used: set[str],
    canonical: str,
    source: str,
    score: float,
    method: str,
) -> None:
    if canonical in fields or source in used:
        return
    fields[canonical] = source
    confidence[canonical] = round(score, 2)
    methods[canonical] = method
    used.add(source)


def _exact_header_matches(
    columns: Sequence[str],
) -> tuple[dict[str, str], dict[str, float], dict[str, str], set[str]]:
    lookup = _normalized_lookup(columns)
    fields: dict[str, str] = {}
    confidence: dict[str, float] = {}
    methods: dict[str, str] = {}
    used: set[str] = set()

    for canonical, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            match = lookup.get(normalize_column_name(alias))
            if match is not None and match not in used:
                _add_match(
                    fields,
                    confidence,
                    methods,
                    used,
                    canonical,
                    match,
                    1.0,
                    "header",
                )
                break
    return fields, confidence, methods, used


def _fuzzy_header_matches(
    columns: Sequence[str],
    fields: dict[str, str],
    confidence: dict[str, float],
    methods: dict[str, str],
    used: set[str],
) -> None:
    for canonical, aliases in FIELD_ALIASES.items():
        if canonical in fields:
            continue
        best_source: str | None = None
        best_score = 0.0
        for source in columns:
            if source in used:
                continue
            normalized = normalize_column_name(source)
            if not normalized:
                continue
            for alias in (*aliases, canonical):
                score = SequenceMatcher(None, normalized, alias).ratio()
                if score > best_score:
                    best_score = score
                    best_source = source
        if best_source is not None and best_score >= _FUZZY_THRESHOLD:
            _add_match(
                fields,
                confidence,
                methods,
                used,
                canonical,
                best_source,
                min(0.95, 0.70 + 0.25 * best_score),
                "header (fuzzy)",
            )


def _text_ratio(series: pd.Series) -> float:
    text = series.astype("string").str.strip()
    non_empty = text[text.ne("") & text.notna()]
    if non_empty.empty:
        return 0.0
    numeric = pd.to_numeric(
        non_empty.str.replace(r"[,\s₹$€£]", "", regex=True),
        errors="coerce",
    )
    return float(numeric.isna().mean())


def _unique_ratio(series: pd.Series) -> float:
    text = series.astype("string").str.strip()
    non_empty = text[text.ne("") & text.notna()]
    if non_empty.empty:
        return 0.0
    return float(non_empty.nunique() / len(non_empty))


def _looks_like_identifier(name: str) -> bool:
    normalized = normalize_column_name(name)
    return any(token in normalized for token in ("id", "code", "number", "no", "ref"))


def _content_fallbacks(
    dataframe: pd.DataFrame,
    fields: dict[str, str],
    confidence: dict[str, float],
    methods: dict[str, str],
    used: set[str],
) -> None:
    """Fill a few missing fields only when the data itself is convincing."""
    available = [column for column in dataframe.columns if column not in used]

    if "order_date" not in fields and available:
        best_source: str | None = None
        best_ratio = 0.0
        for source in available:
            ratio = inspect_dates(dataframe[source].head(500)).valid_ratio
            if ratio > best_ratio:
                best_ratio = ratio
                best_source = source
        if best_source is not None and best_ratio >= 0.60:
            _add_match(
                fields,
                confidence,
                methods,
                used,
                "order_date",
                best_source,
                min(0.75, 0.50 + 0.25 * best_ratio),
                "content",
            )

    if "status" not in fields:
        best_source = None
        best_ratio = 0.0
        for source in dataframe.columns:
            if source in used:
                continue
            values = (
                dataframe[source]
                .astype("string")
                .str.strip()
                .str.lower()
                .replace("", pd.NA)
                .dropna()
            )
            if values.empty:
                continue
            ratio = float(values.isin(_STATUS_WORDS).mean())
            if ratio > best_ratio:
                best_ratio = ratio
                best_source = source
        if best_source is not None and best_ratio >= 0.50:
            _add_match(
                fields,
                confidence,
                methods,
                used,
                "status",
                best_source,
                min(0.80, 0.55 + 0.30 * best_ratio),
                "content",
            )

    if "product" not in fields:
        candidates = [
            source
            for source in dataframe.columns
            if source not in used
            and not _looks_like_identifier(source)
            and _text_ratio(dataframe[source].head(500)) >= 0.80
            and _unique_ratio(dataframe[source].head(500)) >= 0.40
        ]
        if len(candidates) == 1:
            _add_match(
                fields,
                confidence,
                methods,
                used,
                "product",
                candidates[0],
                0.50,
                "content",
            )


def missing_required_for(fields: Mapping[str, str]) -> tuple[str, ...]:
    """Return the required field labels that are absent from a mapping."""
    missing = [FIELD_LABELS[field] for field in REQUIRED_FIELDS if field not in fields]
    if not any(field in fields for field in PRICE_FIELDS):
        missing.append("unit_price or line_total")
    return tuple(missing)


def detect_column_mapping(columns: Sequence[str]) -> ColumnMapping:
    """Detect canonical fields from a sequence of CSV column names."""
    return detect_dataframe_mapping(pd.DataFrame(columns=list(columns)))


def detect_dataframe_mapping(dataframe: pd.DataFrame) -> ColumnMapping:
    """Detect canonical fields using headers and a little content inspection."""
    fields, confidence, methods, used = _exact_header_matches(list(dataframe.columns))
    _fuzzy_header_matches(list(dataframe.columns), fields, confidence, methods, used)
    _content_fallbacks(dataframe, fields, confidence, methods, used)

    return ColumnMapping(
        fields=fields,
        missing_required=missing_required_for(fields),
        confidence=confidence,
        methods=methods,
    )


def resolve_mapping(
    columns: Sequence[str],
    overrides: Mapping[str, str | None],
) -> ColumnMapping:
    """Apply user overrides to automatic detection.

    An override value of ``None`` or ``""`` removes a field. A source column can
    only be assigned to one canonical field.
    """
    base = detect_column_mapping(columns)
    fields = dict(base.fields)
    confidence = dict(base.confidence)
    methods = dict(base.methods)

    for canonical in FIELD_ORDER:
        if canonical not in overrides:
            continue
        source = overrides[canonical]
        if source in (None, ""):
            fields.pop(canonical, None)
            confidence.pop(canonical, None)
            methods.pop(canonical, None)
            continue
        if source not in columns:
            raise MappingError(f"Column {source!r} is not present in this file.")
        fields[canonical] = str(source)
        confidence[canonical] = 1.0
        methods[canonical] = "manual"

    assigned: dict[str, str] = {}
    for canonical, source in fields.items():
        if source in assigned:
            raise MappingError(
                f"Column {source!r} is mapped to both {assigned[source]!r} and {canonical!r}."
            )
        assigned[source] = canonical

    return ColumnMapping(
        fields=fields,
        missing_required=missing_required_for(fields),
        confidence=confidence,
        methods=methods,
    )


def mapping_table_rows(mapping: ColumnMapping) -> list[dict[str, str]]:
    """Build display rows describing each canonical field's detection."""
    rows: list[dict[str, str]] = []
    for field in FIELD_ORDER:
        source = mapping.fields.get(field)
        confidence = mapping.confidence.get(field)
        if source is None:
            status = "Not detected"
            confidence_text = "—"
        else:
            confidence_text = f"{confidence:.0%}" if confidence is not None else "—"
            if confidence is not None and confidence < LOW_CONFIDENCE_THRESHOLD:
                status = "Review suggested"
            else:
                status = "Detected"
        rows.append(
            {
                "Field": FIELD_LABELS[field],
                "Source column": source or "—",
                "Confidence": confidence_text,
                "Method": mapping.methods.get(field, "—"),
                "Status": status,
            }
        )
    return rows
