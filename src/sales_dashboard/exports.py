"""Pure helpers for exporting cleaned data and data-quality reports."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from sales_dashboard.models import ValidationReport

CSV_MIME = "text/csv"
QUALITY_REPORT_COLUMNS: tuple[str, ...] = (
    "Section",
    "Code",
    "Severity",
    "Description",
    "Affected rows",
    "Action taken",
    "Examples",
    "Value",
)
_SEVERITY_LABELS = {"error": "Error", "warning": "Warning", "info": "Info"}


def _sanitize_component(value: str, fallback: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return sanitized or fallback


def export_filename(
    source_filename: str,
    label: str,
    *,
    timestamp: datetime | None = None,
    extension: str = "csv",
) -> str:
    """Build a safe, timestamped download name from the source file and label."""
    stem = _sanitize_component(Path(source_filename).stem, "sales_data")
    suffix = _sanitize_component(label, "export")
    stamp = (timestamp or datetime.now()).strftime("%Y%m%d_%H%M%S")
    return f"{stem}_{suffix}_{stamp}.{extension}"


def dataframe_to_csv_bytes(dataframe: pd.DataFrame, *, bom: bool = True) -> bytes:
    """Serialise a dataframe to CSV, optionally with a UTF-8 BOM for Excel."""
    encoding = "utf-8-sig" if bom else "utf-8"
    return dataframe.to_csv(index=False, lineterminator="\n").encode(encoding)


def select_columns(dataframe: pd.DataFrame, columns: list[str] | tuple[str, ...]) -> pd.DataFrame:
    """Return the requested columns in order, validating that they all exist."""
    requested = list(columns)
    if not requested:
        raise ValueError("Select at least one column to export.")
    missing = [column for column in requested if column not in dataframe.columns]
    if missing:
        raise KeyError("Unknown columns: " + ", ".join(missing))
    return dataframe.loc[:, requested]


def quality_report_frame(
    report: ValidationReport,
    *,
    source_filename: str,
    revenue_source: str,
    date_format_used: str | None,
) -> pd.DataFrame:
    """Build a tidy quality-report table with a summary section and issue rows."""
    summary = [
        ("source_file", "Source file", source_filename),
        ("rows_input", "Rows in uploaded file", report.rows_input),
        ("rows_output", "Usable rows", report.rows_output),
        ("rows_dropped", "Rows removed", report.rows_dropped),
        ("dropped_ratio", "Share of rows removed", f"{report.dropped_ratio:.1%}"),
        ("blocked", "Analysis blocked", "Yes" if report.blocked else "No"),
        ("block_reason", "Block reason", report.block_reason or ""),
        ("date_format", "Date format used", date_format_used or "auto"),
        ("revenue_source", "Revenue source", revenue_source),
        ("issue_count", "Reported issues", len(report.issues)),
    ]
    rows: list[dict[str, object]] = [
        {
            "Section": "Summary",
            "Code": code,
            "Severity": "",
            "Description": description,
            "Affected rows": "",
            "Action taken": "",
            "Examples": "",
            "Value": value,
        }
        for code, description, value in summary
    ]
    rows.extend(
        {
            "Section": "Issue",
            "Code": issue.code,
            "Severity": _SEVERITY_LABELS.get(issue.severity, issue.severity.title()),
            "Description": issue.description,
            "Affected rows": issue.affected_rows,
            "Action taken": issue.action_taken,
            "Examples": issue.example_text,
            "Value": "",
        }
        for issue in report.issues
    )
    return pd.DataFrame(rows, columns=list(QUALITY_REPORT_COLUMNS))


def quality_report_csv_bytes(
    report: ValidationReport,
    *,
    source_filename: str,
    revenue_source: str,
    date_format_used: str | None,
) -> bytes:
    """Serialise a quality report to downloadable CSV bytes."""
    frame = quality_report_frame(
        report,
        source_filename=source_filename,
        revenue_source=revenue_source,
        date_format_used=date_format_used,
    )
    return dataframe_to_csv_bytes(frame)
