"""Typed containers shared across the data and UI layers."""

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

import pandas as pd

Severity = Literal["error", "warning", "info"]
DateFormatDecision = Literal["auto", "DMY", "MDY"]
DatePreset = Literal[
    "all_time",
    "last_7_days",
    "last_30_days",
    "last_90_days",
    "this_month",
    "this_year",
    "custom",
]
TrendGranularity = Literal["daily", "weekly", "monthly"]


@dataclass(frozen=True)
class ColumnMapping:
    """Maps canonical field names to columns found in the uploaded file."""

    fields: dict[str, str]
    missing_required: tuple[str, ...] = ()
    confidence: dict[str, float] = field(default_factory=dict)
    methods: dict[str, str] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        """Return True when every required field was detected."""
        return not self.missing_required

    def source_for(self, canonical_name: str) -> str | None:
        """Return the source column for a canonical field, if present."""
        return self.fields.get(canonical_name)

    def confidence_for(self, canonical_name: str) -> float | None:
        """Return the 0-1 confidence for a detected field, if available."""
        return self.confidence.get(canonical_name)

    @property
    def low_confidence_fields(self) -> tuple[str, ...]:
        """Return detected fields that deserve a manual review."""
        return tuple(name for name in self.fields if self.confidence.get(name, 1.0) < 0.75)

    @property
    def requires_review(self) -> bool:
        """Return True when mapping is incomplete or contains uncertain matches."""
        return (not self.is_complete) or bool(self.low_confidence_fields)


@dataclass(frozen=True)
class ValidationIssue:
    """One row in the structured data-quality report."""

    severity: Severity
    code: str
    description: str
    affected_rows: int
    action_taken: str
    examples: tuple[str, ...] = ()

    @property
    def affected_label(self) -> str:
        """Return a human-readable row count for display."""
        if self.affected_rows == 0:
            return "0 rows"
        if self.affected_rows == 1:
            return "1 row"
        return f"{self.affected_rows:,} rows"

    @property
    def example_text(self) -> str:
        """Return examples joined for a table cell."""
        return "; ".join(self.examples) if self.examples else "—"


@dataclass(frozen=True)
class ValidationReport:
    """Structured validation result for the cleaning run."""

    issues: tuple[ValidationIssue, ...]
    rows_input: int
    rows_output: int
    rows_dropped: int
    blocked: bool = False
    block_reason: str | None = None
    date_format_used: str | None = None

    @property
    def dropped_ratio(self) -> float:
        """Return the share of input rows that were removed."""
        if self.rows_input <= 0:
            return 0.0
        return self.rows_dropped / self.rows_input

    @property
    def should_warn_about_drops(self) -> bool:
        """Return True when more than 20% of rows were removed."""
        return self.rows_dropped > 0 and self.dropped_ratio > 0.20

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        """Return error-level issues."""
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        """Return warning-level issues."""
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    @property
    def info(self) -> tuple[ValidationIssue, ...]:
        """Return informational issues."""
        return tuple(issue for issue in self.issues if issue.severity == "info")

    def issue_count(self, severity: Severity) -> int:
        """Return the number of issues at a severity level."""
        return sum(1 for issue in self.issues if issue.severity == severity)


@dataclass(frozen=True)
class DatasetProfile:
    """Lightweight, read-only summary shown on the Home page."""

    row_count: int
    column_count: int
    missing_cells: int
    duplicate_rows: int
    date_min: date | None = None
    date_max: date | None = None
    order_count: int | None = None
    product_count: int | None = None
    category_count: int | None = None
    region_count: int | None = None
    net_revenue: float | None = None


@dataclass(frozen=True)
class LoadedDataset:
    """A parsed dataset plus the metadata needed to describe it."""

    dataframe: pd.DataFrame
    filename: str
    source: Literal["demo", "upload"]
    size_bytes: int
    encoding: str
    delimiter: str
    mapping: ColumnMapping
    profile: DatasetProfile
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CleanedDataset:
    """A cleaned, analysis-ready dataset and its quality report."""

    dataframe: pd.DataFrame
    mapping: ColumnMapping
    report: ValidationReport
    source_filename: str
    date_format_used: str | None = None
    revenue_source: str = "not available"
    order_id_available: bool = False

    @property
    def is_blocked(self) -> bool:
        """Return True when no usable rows remain."""
        return self.report.blocked


@dataclass(frozen=True)
class FilterState:
    """All choices that define the dashboard's filtered view."""

    start_date: date
    end_date: date
    preset: DatePreset = "all_time"
    categories: tuple[str, ...] = ()
    regions: tuple[str, ...] = ()
    products: tuple[str, ...] = ()
    statuses: tuple[str, ...] = ()

    @property
    def date_range_days(self) -> int:
        """Return the inclusive number of days in the selected range."""
        return max((self.end_date - self.start_date).days + 1, 0)

    def with_dates(self, start_date: date, end_date: date) -> "FilterState":
        """Return a copy with a different date range."""
        return FilterState(
            start_date=start_date,
            end_date=end_date,
            preset=self.preset,
            categories=self.categories,
            regions=self.regions,
            products=self.products,
            statuses=self.statuses,
        )


@dataclass(frozen=True)
class KpiSnapshot:
    """The five headline metrics for one period."""

    total_revenue: float = 0.0
    total_orders: int = 0
    total_units: float = 0.0
    total_products: int = 0
    rows: int = 0
    order_id_available: bool = False

    @property
    def average_order_value(self) -> float:
        """Return revenue per order, or zero when there are no orders."""
        if self.total_orders <= 0:
            return 0.0
        return self.total_revenue / self.total_orders

    def value_for(self, key: str) -> float:
        """Return one KPI by its stable dashboard key."""
        values = {
            "total_revenue": self.total_revenue,
            "total_orders": float(self.total_orders),
            "average_order_value": self.average_order_value,
            "total_units": self.total_units,
            "total_products": float(self.total_products),
        }
        try:
            return values[key]
        except KeyError as exc:
            raise KeyError(f"Unknown KPI key: {key!r}") from exc


@dataclass(frozen=True)
class KpiComparison:
    """A current KPI value compared with the preceding equal-length period."""

    key: str
    current: float
    previous: float
    absolute_change: float
    percent_change: float | None
    previous_available: bool


@dataclass(frozen=True)
class DashboardMetrics:
    """Current and previous KPI snapshots plus the period they describe."""

    current: KpiSnapshot
    previous: KpiSnapshot
    comparisons: tuple[KpiComparison, ...]
    current_period: tuple[date, date]
    previous_period: tuple[date, date]
    previous_rows: int
    order_id_available: bool

    def comparison_for(self, key: str) -> KpiComparison:
        """Return the comparison for one KPI key."""
        for comparison in self.comparisons:
            if comparison.key == key:
                return comparison
        raise KeyError(f"Unknown KPI key: {key!r}")


@dataclass(frozen=True)
class Insight:
    """One deterministic, data-backed statement for the Overview page."""

    kind: str
    title: str
    body: str


@dataclass(frozen=True)
class ParetoThreshold:
    """The first product that reaches the 80% cumulative-revenue mark."""

    product: str
    rank: int
    cumulative_share: float
