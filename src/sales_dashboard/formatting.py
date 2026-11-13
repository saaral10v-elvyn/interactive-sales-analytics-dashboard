"""Display formatting helpers with INR as the default currency."""

import math
from datetime import date

from sales_dashboard.config import CURRENCY_SYMBOL


def _as_float(value: float | int | None) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return numeric


def _group_indian(digits: str) -> str:
    """Group digits using the Indian numbering system."""
    if len(digits) <= 3:
        return digits

    head, tail = digits[:-3], digits[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join([*groups, tail])


def format_number(value: float | int | None, decimals: int = 0) -> str:
    """Format a number using Indian digit grouping."""
    numeric = _as_float(value)
    if numeric is None:
        return "—"

    rounded = f"{abs(numeric):.{decimals}f}"
    integer_part, _, decimal_part = rounded.partition(".")
    grouped = _group_indian(integer_part)
    sign = "-" if numeric < 0 else ""
    if decimals and decimal_part:
        return f"{sign}{grouped}.{decimal_part}"
    return f"{sign}{grouped}"


def format_inr(
    value: float | int | None,
    *,
    compact: bool = False,
    decimals: int = 0,
) -> str:
    """Format a value as Indian rupees, optionally in lakh/crore shorthand."""
    numeric = _as_float(value)
    if numeric is None:
        return "—"

    sign = "-" if numeric < 0 else ""
    absolute = abs(numeric)

    if compact:
        if absolute >= 10_000_000:
            return f"{sign}{CURRENCY_SYMBOL}{absolute / 10_000_000:.2f} Cr"
        if absolute >= 100_000:
            return f"{sign}{CURRENCY_SYMBOL}{absolute / 100_000:.2f} L"
        if absolute >= 1_000:
            return f"{sign}{CURRENCY_SYMBOL}{absolute / 1_000:.1f} K"

    return f"{sign}{CURRENCY_SYMBOL}{format_number(absolute, decimals=decimals)}"


def format_bytes(size: int | float | None) -> str:
    """Format a file size for display."""
    numeric = _as_float(size)
    if numeric is None or numeric < 0:
        return "—"
    if numeric < 1024:
        return f"{int(numeric)} B"
    if numeric < 1024**2:
        return f"{numeric / 1024:.1f} KB"
    return f"{numeric / 1024**2:.1f} MB"


def format_date(value: date | None, fmt: str = "%d %b %Y") -> str:
    """Format a date, returning an em dash when it is missing."""
    if value is None:
        return "—"
    return value.strftime(fmt)


def format_date_range(
    start: date | None,
    end: date | None,
    fmt: str = "%d %b %Y",
) -> str:
    """Format a date range, handling missing endpoints."""
    if start is None and end is None:
        return "—"
    if start is None:
        return f"Until {format_date(end, fmt)}"
    if end is None:
        return f"From {format_date(start, fmt)}"
    return f"{format_date(start, fmt)} – {format_date(end, fmt)}"
