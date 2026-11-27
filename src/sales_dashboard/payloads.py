"""JSON serialisers shared by the HTTP API and the frozen parity fixtures.

The functions here work directly on the domain dataclasses and DataFrames, so
the FastAPI layer and the golden files describe exactly the same shapes. None of
this imports a web framework: the API is a thin wrapper around these builders.

Floats are rounded to six decimals to keep fixtures stable across harmless
changes in summation order while still failing on real drift.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

from sales_dashboard.models import (
    CleanedDataset,
    ColumnMapping,
    FilterState,
    LoadedDataset,
    ValidationReport,
)
from sales_dashboard.schema import mapping_table_rows

PREVIEW_ROWS = 5
FLOAT_PRECISION = 6


def _round_float(value: float) -> float | None:
    if not math.isfinite(value):
        return None
    rounded = round(value, FLOAT_PRECISION)
    return 0.0 if rounded == 0 else rounded


def jsonable(value: Any) -> Any:
    """Convert a domain value into a stable, comparable JSON structure."""
    if value is None or value is pd.NaT or value is pd.NA:
        return None
    if isinstance(value, pd.DataFrame):
        return records(value)
    if isinstance(value, pd.Series):
        return [jsonable(item) for item in value.tolist()]
    if isinstance(value, (pd.Timestamp, datetime)):
        return None if pd.isna(value) else value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):  # bool before int: bool is an int subclass
        return bool(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return _round_float(float(value))
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return _round_float(value)
    if isinstance(value, str):
        return value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: jsonable(getattr(value, field.name)) for field in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [jsonable(item) for item in value]
    raise TypeError(f"Cannot serialise {type(value).__name__} for JSON output")


def records(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    """Render a dataframe as a list of JSON-safe row dictionaries."""
    columns = [str(column) for column in dataframe.columns]
    return [
        {column: jsonable(value) for column, value in zip(columns, row, strict=True)}
        for row in dataframe.itertuples(index=False, name=None)
    ]


def mapping_summary(mapping: ColumnMapping) -> dict[str, Any]:
    """Describe a detected or manual mapping, including its review flags."""
    return {
        "fields": dict(mapping.fields),
        "missing_required": list(mapping.missing_required),
        "confidence": dict(mapping.confidence),
        "methods": dict(mapping.methods),
        "is_complete": mapping.is_complete,
        "requires_review": mapping.requires_review,
        "low_confidence_fields": list(mapping.low_confidence_fields),
        "table": mapping_table_rows(mapping),
    }


def dataset_summary(loaded: LoadedDataset) -> dict[str, Any]:
    """Describe a freshly loaded file: profile, mapping, dtypes and preview."""
    dataframe = loaded.dataframe
    return {
        "filename": loaded.filename,
        "source": loaded.source,
        "size_bytes": loaded.size_bytes,
        "encoding": loaded.encoding,
        "delimiter": loaded.delimiter,
        "row_count": len(dataframe),
        "column_count": len(dataframe.columns),
        "columns": [str(column) for column in dataframe.columns],
        "warnings": list(loaded.warnings),
        "profile": jsonable(loaded.profile),
        "mapping": mapping_summary(loaded.mapping),
        "dtypes": {str(column): str(dtype) for column, dtype in dataframe.dtypes.items()},
        "preview": records(dataframe.head(PREVIEW_ROWS)),
    }


def report_summary(report: ValidationReport) -> dict[str, Any]:
    """Describe a validation report, including derived severity counts."""
    return {
        "rows_input": report.rows_input,
        "rows_output": report.rows_output,
        "rows_dropped": report.rows_dropped,
        "blocked": report.blocked,
        "block_reason": report.block_reason,
        "date_format_used": report.date_format_used,
        "dropped_ratio": report.dropped_ratio,
        "should_warn_about_drops": report.should_warn_about_drops,
        "issue_counts": {
            severity: report.issue_count(severity) for severity in ("error", "warning", "info")
        },
        "issues": [
            {
                "severity": issue.severity,
                "code": issue.code,
                "description": issue.description,
                "affected_rows": issue.affected_rows,
                "affected_label": issue.affected_label,
                "action_taken": issue.action_taken,
                "examples": list(issue.examples),
                "example_text": issue.example_text,
            }
            for issue in report.issues
        ],
    }


def filter_state_dict(state: FilterState) -> dict[str, Any]:
    """Serialise a filter state for the wire and the frozen fixtures."""
    return {
        "start_date": state.start_date,
        "end_date": state.end_date,
        "preset": state.preset,
        "categories": list(state.categories),
        "regions": list(state.regions),
        "products": list(state.products),
        "statuses": list(state.statuses),
    }


def cleaning_summary(cleaned: CleanedDataset) -> dict[str, Any]:
    """Describe a cleaned dataset, its quality report and its preview."""
    dataframe = cleaned.dataframe
    returns_kept = 0
    if "quantity" in dataframe.columns and not dataframe.empty:
        returns_kept = int((pd.to_numeric(dataframe["quantity"], errors="coerce") < 0).sum())

    return {
        "rows": len(dataframe),
        "columns": [str(column) for column in dataframe.columns],
        "dtypes": {str(column): str(dtype) for column, dtype in dataframe.dtypes.items()},
        "revenue_source": cleaned.revenue_source,
        "order_id_available": cleaned.order_id_available,
        "date_format_used": cleaned.date_format_used,
        "returns_kept": returns_kept,
        "report": report_summary(cleaned.report),
        "preview": records(dataframe.head(PREVIEW_ROWS)),
    }
