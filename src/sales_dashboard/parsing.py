"""Small, reusable parsing helpers for values stored as text."""

import re

import pandas as pd

_CURRENCY_AND_SPACE = re.compile(r"[₹$€£,\s]")
_NEGATIVE_PARENS = re.compile(r"^\((.*)\)$")
_NUMERIC_KEEP = re.compile(r"[^0-9eE+\-.]")


def clean_numeric_text(series: pd.Series) -> pd.Series:
    """Strip currency symbols, grouping commas and whitespace from numbers."""
    text = series.astype("string").str.strip()
    text = text.str.replace(_NEGATIVE_PARENS, r"-\1", regex=True)
    text = text.str.replace(_CURRENCY_AND_SPACE, "", regex=True)
    text = text.str.replace(_NUMERIC_KEEP, "", regex=True)
    return text


def to_numeric(series: pd.Series) -> pd.Series:
    """Convert text that may contain currency formatting into numbers."""
    return pd.to_numeric(clean_numeric_text(series), errors="coerce")


def parse_dates(series: pd.Series) -> pd.Series:
    """Parse dates defensively, returning NaT for unreadable values."""
    text = series.astype("string").str.strip()
    return pd.to_datetime(text, errors="coerce", format="mixed")
