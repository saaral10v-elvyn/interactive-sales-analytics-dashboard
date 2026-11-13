"""Dataset summaries for the Home page.

This is deliberately lightweight. Full validation and cleaning live in a later
milestone so the Home page can describe a file without mutating it.
"""

from datetime import date

import pandas as pd

from sales_dashboard.dates import inspect_dates, parse_dates_with_decision
from sales_dashboard.models import ColumnMapping, DatasetProfile
from sales_dashboard.parsing import to_numeric


def _mapped_series(
    dataframe: pd.DataFrame,
    mapping: ColumnMapping,
    field: str,
) -> pd.Series | None:
    source = mapping.source_for(field)
    if source is None or source not in dataframe.columns:
        return None
    return dataframe[source]


def _count_unique(series: pd.Series | None) -> int | None:
    if series is None:
        return None
    text = series.astype("string").str.strip()
    usable = text[text.ne("") & text.notna()]
    return int(usable.nunique())


def profile_dataset(dataframe: pd.DataFrame, mapping: ColumnMapping) -> DatasetProfile:
    """Build the small summary shown after a file is loaded."""
    missing_cells = int((dataframe.isna() | dataframe.eq("")).sum().sum())
    duplicate_rows = int(dataframe.duplicated().sum())

    date_min: date | None = None
    date_max: date | None = None
    date_series = _mapped_series(dataframe, mapping, "order_date")
    if date_series is not None:
        inspection = inspect_dates(date_series)
        # Do not present a guessed date range while DMY/MDY is unresolved.
        if not inspection.requires_decision:
            parsed = parse_dates_with_decision(date_series, "auto", inspection=inspection)
            valid = parsed.dropna()
            if not valid.empty:
                date_min = valid.min().date()
                date_max = valid.max().date()

    net_revenue: float | None = None
    line_total = _mapped_series(dataframe, mapping, "line_total")
    if line_total is not None:
        amounts = to_numeric(line_total)
        if amounts.notna().any():
            net_revenue = float(amounts.sum())

    return DatasetProfile(
        row_count=len(dataframe),
        column_count=len(dataframe.columns),
        missing_cells=missing_cells,
        duplicate_rows=duplicate_rows,
        date_min=date_min,
        date_max=date_max,
        order_count=_count_unique(_mapped_series(dataframe, mapping, "order_id")),
        product_count=_count_unique(_mapped_series(dataframe, mapping, "product")),
        category_count=_count_unique(_mapped_series(dataframe, mapping, "category")),
        region_count=_count_unique(_mapped_series(dataframe, mapping, "region")),
        net_revenue=net_revenue,
    )
