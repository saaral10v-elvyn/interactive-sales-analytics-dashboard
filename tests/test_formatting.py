"""Tests for currency, number and date formatting."""

from datetime import date

from sales_dashboard.formatting import (
    format_bytes,
    format_date_range,
    format_inr,
    format_number,
)


def test_indian_digit_grouping() -> None:
    assert format_number(1_234_567) == "12,34,567"
    assert format_number(123_456) == "1,23,456"
    assert format_number(999) == "999"
    assert format_number(-1_500) == "-1,500"


def test_inr_formatting() -> None:
    assert format_inr(1_234_567) == "₹12,34,567"
    assert format_inr(12_345_678, compact=True) == "₹1.23 Cr"
    assert format_inr(456_789, compact=True) == "₹4.57 L"
    assert format_inr(12_500, compact=True) == "₹12.5 K"
    assert format_inr(-1_500) == "-₹1,500"
    assert format_inr(None) == "—"


def test_file_size_formatting() -> None:
    assert format_bytes(512) == "512 B"
    assert format_bytes(1_536) == "1.5 KB"
    assert format_bytes(2 * 1024 * 1024) == "2.0 MB"


def test_date_range_formatting() -> None:
    assert format_date_range(date(2025, 5, 1), date(2026, 10, 31)) == "01 May 2025 – 31 Oct 2026"
    assert format_date_range(None, None) == "—"
