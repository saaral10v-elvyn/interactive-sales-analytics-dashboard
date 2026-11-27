"""Reusable business metrics for the dashboard.

Every function here is pure Pandas: no web framework imports and no hidden
state. The Overview page applies the shared filters once and then calls these
helpers, which guarantees that cards, charts and insights all describe the same
rows.
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from sales_dashboard.filters import apply_filters, previous_period
from sales_dashboard.formatting import format_date, format_inr, format_number
from sales_dashboard.models import (
    DashboardMetrics,
    FilterState,
    Insight,
    KpiComparison,
    KpiSnapshot,
    ParetoThreshold,
    TrendGranularity,
)

KPI_KEYS: tuple[str, ...] = (
    "total_revenue",
    "total_orders",
    "average_order_value",
    "total_units",
    "total_products",
)

KPI_LABELS: dict[str, str] = {
    "total_revenue": "Total revenue",
    "total_orders": "Total orders",
    "average_order_value": "Average order value",
    "total_units": "Total units sold",
    "total_products": "Total products",
}

KPI_CURRENCY: dict[str, bool] = {
    "total_revenue": True,
    "total_orders": False,
    "average_order_value": True,
    "total_units": False,
    "total_products": False,
}

TREND_COLUMNS: tuple[str, ...] = ("period", "revenue", "orders", "units")
CATEGORY_COLUMNS: tuple[str, ...] = ("category", "revenue", "units", "share")
PRODUCT_COLUMNS: tuple[str, ...] = ("product", "revenue", "units")
PRODUCT_PERFORMANCE_COLUMNS: tuple[str, ...] = (
    "product",
    "revenue",
    "units",
    "orders",
    "average_order_value",
    "share",
)
PARETO_COLUMNS: tuple[str, ...] = (
    "rank",
    "product",
    "revenue",
    "cumulative_revenue",
    "cumulative_share",
)
REGION_COLUMNS: tuple[str, ...] = (
    "region",
    "revenue",
    "orders",
    "units",
    "average_order_value",
    "share",
)
REGION_CATEGORY_COLUMNS: tuple[str, ...] = ("region", "category", "revenue")
REGIONAL_TREND_COLUMNS: tuple[str, ...] = ("period", "region", "revenue")

UNCATEGORISED_LABEL = "Uncategorised"
UNKNOWN_REGION_LABEL = "Unknown region"


def _numeric(dataframe: pd.DataFrame, column: str) -> pd.Series:
    if column not in dataframe.columns:
        return pd.Series(0.0, index=dataframe.index, dtype="float64")
    return pd.to_numeric(dataframe[column], errors="coerce").fillna(0.0)


def _text(dataframe: pd.DataFrame, column: str) -> pd.Series:
    if column not in dataframe.columns:
        return pd.Series(pd.NA, index=dataframe.index, dtype="string")
    return dataframe[column].astype("string").str.strip()


def _order_counts(
    dataframe: pd.DataFrame,
    group_keys: str | list[str],
    *,
    order_id_available: bool,
) -> pd.Series:
    """Count distinct orders per group, counting blank IDs as separate orders."""
    if dataframe.empty:
        return pd.Series(dtype="int64")
    if order_id_available and "order_id" in dataframe.columns:
        ids = _text(dataframe, "order_id")
        usable = ids.ne("") & ids.notna()
        distinct = (
            dataframe.loc[usable]
            .assign(_order_id=ids[usable])
            .groupby(group_keys)["_order_id"]
            .nunique()
        )
        blank_rows = dataframe.loc[~usable].groupby(group_keys).size()
        return distinct.add(blank_rows, fill_value=0).astype("int64")
    return dataframe.groupby(group_keys).size().astype("int64")


def count_orders(dataframe: pd.DataFrame, *, order_id_available: bool) -> int:
    """Count distinct orders, or rows when order IDs are unavailable.

    A blank order ID cannot be grouped, so each blank row is counted as its own
    order instead of being silently ignored. This keeps the order count honest
    when a file has a few missing identifiers.
    """
    if dataframe.empty:
        return 0
    if not order_id_available or "order_id" not in dataframe.columns:
        return int(len(dataframe))

    ids = _text(dataframe, "order_id")
    usable = ids[ids.ne("") & ids.notna()]
    blank_rows = int((ids.isna() | ids.eq("")).sum())
    return int(usable.nunique()) + blank_rows


def compute_kpis(
    dataframe: pd.DataFrame,
    *,
    order_id_available: bool,
) -> KpiSnapshot:
    """Calculate the five headline metrics for a filtered dataframe."""
    if dataframe.empty:
        return KpiSnapshot(order_id_available=order_id_available)

    products = _text(dataframe, "product")
    usable_products = products[products.ne("") & products.notna()]

    return KpiSnapshot(
        total_revenue=float(_numeric(dataframe, "revenue").sum()),
        total_orders=count_orders(dataframe, order_id_available=order_id_available),
        total_units=float(_numeric(dataframe, "quantity").sum()),
        total_products=int(usable_products.nunique()),
        rows=int(len(dataframe)),
        order_id_available=order_id_available,
    )


def percentage_change(current: float, previous: float) -> float | None:
    """Return the percentage change, or ``None`` when the base is zero.

    The absolute value of the previous base is used so the sign always means
    "more" or "less", even when a returns-heavy period has negative revenue.
    """
    if previous == 0:
        return None
    return (current - previous) / abs(previous) * 100.0


def compare_snapshots(
    current: KpiSnapshot,
    previous: KpiSnapshot,
    *,
    previous_available: bool,
) -> tuple[KpiComparison, ...]:
    """Compare every KPI with the same KPI in the preceding period."""
    comparisons: list[KpiComparison] = []
    for key in KPI_KEYS:
        current_value = current.value_for(key)
        previous_value = previous.value_for(key)
        comparisons.append(
            KpiComparison(
                key=key,
                current=current_value,
                previous=previous_value,
                absolute_change=current_value - previous_value,
                percent_change=percentage_change(current_value, previous_value),
                previous_available=previous_available,
            )
        )
    return tuple(comparisons)


def compute_dashboard_metrics(
    dataframe: pd.DataFrame,
    filter_state: FilterState,
    *,
    order_id_available: bool,
) -> DashboardMetrics:
    """Build current/previous KPI snapshots for the selected filters."""
    current_rows = apply_filters(dataframe, filter_state)
    previous_start, previous_end = previous_period(
        filter_state.start_date,
        filter_state.end_date,
    )
    previous_state = replace(
        filter_state,
        start_date=previous_start,
        end_date=previous_end,
        preset="custom",
    )
    previous_rows = apply_filters(dataframe, previous_state)

    current = compute_kpis(current_rows, order_id_available=order_id_available)
    previous = compute_kpis(previous_rows, order_id_available=order_id_available)
    previous_available = not previous_rows.empty

    return DashboardMetrics(
        current=current,
        previous=previous,
        comparisons=compare_snapshots(
            current,
            previous,
            previous_available=previous_available,
        ),
        current_period=(filter_state.start_date, filter_state.end_date),
        previous_period=(previous_start, previous_end),
        previous_rows=int(len(previous_rows)),
        order_id_available=order_id_available,
    )


def _period_values(
    dates: pd.Series,
    granularity: TrendGranularity,
) -> pd.Series:
    if granularity == "daily":
        return dates.dt.normalize()
    if granularity == "weekly":
        return dates.dt.to_period("W-SUN").dt.start_time
    if granularity == "monthly":
        return dates.dt.to_period("M").dt.start_time
    raise ValueError(f"Unknown trend granularity: {granularity!r}")


def _full_period_index(
    first: pd.Timestamp,
    last: pd.Timestamp,
    granularity: TrendGranularity,
) -> pd.DatetimeIndex:
    if granularity == "daily":
        return pd.date_range(first, last, freq="D")
    if granularity == "weekly":
        return pd.date_range(first, last, freq="7D")
    if granularity == "monthly":
        return pd.date_range(first, last, freq="MS")
    raise ValueError(f"Unknown trend granularity: {granularity!r}")


def revenue_trend(
    dataframe: pd.DataFrame,
    granularity: TrendGranularity = "monthly",
    *,
    order_id_available: bool,
) -> pd.DataFrame:
    """Aggregate revenue by day, week or month, filling empty periods with zero."""
    if dataframe.empty or "order_date" not in dataframe.columns:
        return pd.DataFrame(columns=list(TREND_COLUMNS))

    frame = dataframe.copy()
    dates = pd.to_datetime(frame["order_date"], errors="coerce")
    frame = frame.loc[dates.notna()].copy()
    if frame.empty:
        return pd.DataFrame(columns=list(TREND_COLUMNS))

    dates = dates.loc[frame.index]
    frame["_period"] = _period_values(dates, granularity)
    frame["_revenue"] = _numeric(frame, "revenue")
    frame["_units"] = _numeric(frame, "quantity")

    grouped = frame.groupby("_period", sort=True).agg(
        revenue=("_revenue", "sum"),
        units=("_units", "sum"),
    )

    grouped["orders"] = _order_counts(
        frame,
        "_period",
        order_id_available=order_id_available,
    ).reindex(grouped.index)

    full_index = _full_period_index(
        grouped.index.min(),
        grouped.index.max(),
        granularity,
    )
    grouped = grouped.reindex(full_index)
    grouped["revenue"] = grouped["revenue"].fillna(0.0)
    grouped["units"] = grouped["units"].fillna(0.0)
    grouped["orders"] = grouped["orders"].fillna(0).astype(int)

    result = grouped.reset_index()
    result = result.rename(columns={result.columns[0]: "period"})
    return result.loc[:, list(TREND_COLUMNS)]


def category_revenue(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Sum net revenue by category, highest first."""
    if dataframe.empty or "category" not in dataframe.columns:
        return pd.DataFrame(columns=list(CATEGORY_COLUMNS))

    frame = dataframe.copy()
    labels = _text(frame, "category")
    frame["_category"] = labels.mask(labels.eq("") | labels.isna(), UNCATEGORISED_LABEL)
    frame["_revenue"] = _numeric(frame, "revenue")
    frame["_units"] = _numeric(frame, "quantity")

    grouped = (
        frame.groupby("_category", sort=False)
        .agg(revenue=("_revenue", "sum"), units=("_units", "sum"))
        .reset_index()
        .rename(columns={"_category": "category"})
        .sort_values("revenue", ascending=False, kind="stable")
        .reset_index(drop=True)
    )
    total = float(grouped["revenue"].sum())
    grouped["share"] = grouped["revenue"] / total if total > 0 else 0.0
    return grouped.loc[:, list(CATEGORY_COLUMNS)]


def product_performance(
    dataframe: pd.DataFrame,
    *,
    order_id_available: bool = False,
) -> pd.DataFrame:
    """Aggregate revenue, units, orders, AOV and revenue share by product.

    Revenue share is left undefined when total net revenue is zero or negative,
    because a percentage of a non-positive base would be misleading.
    """
    if dataframe.empty or "product" not in dataframe.columns:
        return pd.DataFrame(columns=list(PRODUCT_PERFORMANCE_COLUMNS))

    frame = dataframe.copy()
    labels = _text(frame, "product")
    frame = frame.loc[labels.ne("") & labels.notna()].copy()
    if frame.empty:
        return pd.DataFrame(columns=list(PRODUCT_PERFORMANCE_COLUMNS))

    frame["_product"] = _text(frame, "product")
    frame["_revenue"] = _numeric(frame, "revenue")
    frame["_units"] = _numeric(frame, "quantity")

    grouped = frame.groupby("_product", sort=False).agg(
        revenue=("_revenue", "sum"),
        units=("_units", "sum"),
    )
    grouped["orders"] = _order_counts(
        frame,
        "_product",
        order_id_available=order_id_available,
    ).reindex(grouped.index)
    grouped = grouped.reset_index().rename(columns={"_product": "product"})
    grouped["orders"] = grouped["orders"].fillna(0).astype(int)
    grouped["average_order_value"] = 0.0
    has_orders = grouped["orders"] > 0
    grouped.loc[has_orders, "average_order_value"] = (
        grouped.loc[has_orders, "revenue"] / grouped.loc[has_orders, "orders"]
    )

    total = float(grouped["revenue"].sum())
    grouped["share"] = grouped["revenue"] / total if total > 0 else float("nan")
    grouped = grouped.sort_values(
        ["revenue", "product"],
        ascending=[False, True],
        kind="stable",
    ).reset_index(drop=True)
    return grouped.loc[:, list(PRODUCT_PERFORMANCE_COLUMNS)]


def top_products(
    dataframe: pd.DataFrame,
    *,
    limit: int = 10,
    order_id_available: bool = False,
) -> pd.DataFrame:
    """Return the highest-revenue products, ordered from highest to lowest."""
    if limit <= 0:
        return pd.DataFrame(columns=list(PRODUCT_COLUMNS))
    performance = product_performance(
        dataframe,
        order_id_available=order_id_available,
    )
    if performance.empty:
        return pd.DataFrame(columns=list(PRODUCT_COLUMNS))
    return performance.head(limit).loc[:, list(PRODUCT_COLUMNS)].reset_index(drop=True)


def product_pareto(
    dataframe: pd.DataFrame,
    *,
    order_id_available: bool = False,
) -> pd.DataFrame:
    """Build a Pareto table from products with positive net revenue.

    Returns-only products are excluded so the cumulative line ends at exactly
    100% and never implies a misleading contribution above the total.
    """
    performance = product_performance(
        dataframe,
        order_id_available=order_id_available,
    )
    if performance.empty:
        return pd.DataFrame(columns=list(PARETO_COLUMNS))

    positive = performance.loc[performance["revenue"] > 0].reset_index(drop=True)
    if positive.empty:
        return pd.DataFrame(columns=list(PARETO_COLUMNS))

    total = float(positive["revenue"].sum())
    positive.insert(0, "rank", range(1, len(positive) + 1))
    positive["cumulative_revenue"] = positive["revenue"].cumsum()
    positive["cumulative_share"] = positive["cumulative_revenue"] / total
    return positive.loc[:, list(PARETO_COLUMNS)]


def pareto_threshold(data: pd.DataFrame) -> ParetoThreshold | None:
    """Return the first product that reaches 80% cumulative revenue."""
    if data.empty or "cumulative_share" not in data.columns:
        return None
    reached = data.loc[data["cumulative_share"] >= 0.8]
    if reached.empty:
        return None
    row = reached.iloc[0]
    return ParetoThreshold(
        product=str(row["product"]),
        rank=int(row["rank"]),
        cumulative_share=float(row["cumulative_share"]),
    )


def _rows_for_product(dataframe: pd.DataFrame, product: str) -> pd.DataFrame:
    if dataframe.empty or "product" not in dataframe.columns:
        return dataframe.iloc[0:0]
    labels = _text(dataframe, "product")
    return dataframe.loc[labels.eq(product)]


def product_snapshot(
    dataframe: pd.DataFrame,
    product: str,
    *,
    order_id_available: bool,
) -> KpiSnapshot:
    """Return revenue, units, orders and AOV for one product."""
    return compute_kpis(
        _rows_for_product(dataframe, product),
        order_id_available=order_id_available,
    )


def product_revenue_trend(
    dataframe: pd.DataFrame,
    product: str,
    granularity: TrendGranularity = "monthly",
    *,
    order_id_available: bool,
) -> pd.DataFrame:
    """Aggregate one product's revenue by day, week or month."""
    return revenue_trend(
        _rows_for_product(dataframe, product),
        granularity,
        order_id_available=order_id_available,
    )


def regional_performance(
    dataframe: pd.DataFrame,
    *,
    order_id_available: bool = False,
) -> pd.DataFrame:
    """Aggregate revenue, orders, units, AOV and revenue share by region."""
    if dataframe.empty or "region" not in dataframe.columns:
        return pd.DataFrame(columns=list(REGION_COLUMNS))

    frame = dataframe.copy()
    labels = _text(frame, "region")
    frame["_region"] = labels.mask(labels.eq("") | labels.isna(), UNKNOWN_REGION_LABEL)
    frame["_revenue"] = _numeric(frame, "revenue")
    frame["_units"] = _numeric(frame, "quantity")

    grouped = frame.groupby("_region", sort=False).agg(
        revenue=("_revenue", "sum"),
        units=("_units", "sum"),
    )
    grouped["orders"] = _order_counts(
        frame,
        "_region",
        order_id_available=order_id_available,
    ).reindex(grouped.index)
    grouped = grouped.reset_index().rename(columns={"_region": "region"})
    grouped["orders"] = grouped["orders"].fillna(0).astype(int)
    grouped["average_order_value"] = 0.0
    has_orders = grouped["orders"] > 0
    grouped.loc[has_orders, "average_order_value"] = (
        grouped.loc[has_orders, "revenue"] / grouped.loc[has_orders, "orders"]
    )

    total = float(grouped["revenue"].sum())
    grouped["share"] = grouped["revenue"] / total if total > 0 else float("nan")
    grouped = grouped.sort_values(
        ["revenue", "region"],
        ascending=[False, True],
        kind="stable",
    ).reset_index(drop=True)
    return grouped.loc[:, list(REGION_COLUMNS)]


def region_category_revenue(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Return long-form revenue by region and category for a stacked chart."""
    if dataframe.empty or "region" not in dataframe.columns or "category" not in dataframe.columns:
        return pd.DataFrame(columns=list(REGION_CATEGORY_COLUMNS))

    frame = dataframe.copy()
    regions = _text(frame, "region")
    categories = _text(frame, "category")
    frame["_region"] = regions.mask(regions.eq("") | regions.isna(), UNKNOWN_REGION_LABEL)
    frame["_category"] = categories.mask(
        categories.eq("") | categories.isna(),
        UNCATEGORISED_LABEL,
    )
    frame["_revenue"] = _numeric(frame, "revenue")

    grouped = (
        frame.groupby(["_region", "_category"], sort=False)["_revenue"]
        .sum()
        .reset_index()
        .rename(
            columns={
                "_region": "region",
                "_category": "category",
                "_revenue": "revenue",
            }
        )
    )
    region_order = (
        grouped.groupby("region")["revenue"].sum().sort_values(ascending=False, kind="stable").index
    )
    category_order = (
        grouped.groupby("category")["revenue"]
        .sum()
        .sort_values(ascending=False, kind="stable")
        .index
    )
    grouped["_region_order"] = grouped["region"].map(
        {region: index for index, region in enumerate(region_order)}
    )
    grouped["_category_order"] = grouped["category"].map(
        {category: index for index, category in enumerate(category_order)}
    )
    grouped = grouped.sort_values(
        ["_region_order", "_category_order"],
        kind="stable",
    )
    return grouped.loc[:, list(REGION_CATEGORY_COLUMNS)].reset_index(drop=True)


def regional_revenue_trend(
    dataframe: pd.DataFrame,
    granularity: TrendGranularity = "monthly",
) -> pd.DataFrame:
    """Aggregate revenue by region and period, filling missing periods with zero."""
    if (
        dataframe.empty
        or "region" not in dataframe.columns
        or "order_date" not in dataframe.columns
    ):
        return pd.DataFrame(columns=list(REGIONAL_TREND_COLUMNS))

    frame = dataframe.copy()
    dates = pd.to_datetime(frame["order_date"], errors="coerce")
    frame = frame.loc[dates.notna()].copy()
    if frame.empty:
        return pd.DataFrame(columns=list(REGIONAL_TREND_COLUMNS))

    dates = dates.loc[frame.index]
    regions = _text(frame, "region")
    frame["_region"] = regions.mask(regions.eq("") | regions.isna(), UNKNOWN_REGION_LABEL)
    frame["_period"] = _period_values(dates, granularity)
    frame["_revenue"] = _numeric(frame, "revenue")

    grouped = frame.groupby(["_period", "_region"], sort=True)["_revenue"].sum()
    full_index = _full_period_index(
        grouped.index.get_level_values(0).min(),
        grouped.index.get_level_values(0).max(),
        granularity,
    )
    region_order = (
        frame.groupby("_region")["_revenue"].sum().sort_values(ascending=False, kind="stable").index
    )
    complete_index = pd.MultiIndex.from_product(
        [full_index, region_order],
        names=["_period", "_region"],
    )
    grouped = grouped.reindex(complete_index, fill_value=0).reset_index()
    grouped = grouped.rename(
        columns={
            "_period": "period",
            "_region": "region",
            "_revenue": "revenue",
        }
    )
    return grouped.loc[:, list(REGIONAL_TREND_COLUMNS)]


def _category_insights(dataframe: pd.DataFrame) -> list[Insight]:
    data = category_revenue(dataframe)
    if data.empty:
        return []

    top = data.iloc[0]
    revenue = float(top["revenue"])
    category = str(top["category"])
    if revenue <= 0:
        return [
            Insight(
                kind="category",
                title="No category generated positive revenue",
                body=("Returns and adjustments offset category sales in the selected period."),
            )
        ]

    share = float(top["share"])
    share_text = f" ({share:.1%} of net revenue)" if share > 0 else ""
    return [
        Insight(
            kind="category",
            title=f"{category} is the top category",
            body=(
                f"{format_inr(revenue)} in net revenue{share_text} from "
                f"{format_number(float(top['units']))} units."
            ),
        )
    ]


def _product_insights(dataframe: pd.DataFrame) -> list[Insight]:
    data = top_products(dataframe, limit=1)
    if data.empty:
        return []

    top = data.iloc[0]
    revenue = float(top["revenue"])
    product = str(top["product"])
    if revenue <= 0:
        return [
            Insight(
                kind="product",
                title="No product generated positive revenue",
                body=("Returns and adjustments offset product sales in the selected period."),
            )
        ]
    return [
        Insight(
            kind="product",
            title=f"{product} is the top product",
            body=(
                f"{format_inr(revenue)} in net revenue from "
                f"{format_number(float(top['units']))} units."
            ),
        )
    ]


def _trend_insight(dataframe: pd.DataFrame) -> list[Insight]:
    if dataframe.empty or "order_date" not in dataframe.columns:
        return []
    dates = pd.to_datetime(dataframe["order_date"], errors="coerce")
    valid = dates.dropna()
    if valid.empty:
        return []

    first_day = valid.min().normalize()
    last_day = valid.max().normalize()
    if first_day == last_day:
        return []

    midpoint = first_day + (last_day - first_day) / 2
    revenue = _numeric(dataframe, "revenue")
    first_half = float(revenue[dates <= midpoint].sum())
    second_half = float(revenue[dates > midpoint].sum())
    total = first_half + second_half

    if total < 0:
        return [
            Insight(
                kind="trend",
                title="Net revenue is negative for this selection",
                body=("Returns and adjustments outweighed sales in the selected period."),
            )
        ]

    change = second_half - first_half
    threshold = max(abs(first_half), abs(second_half)) * 0.05
    if change > threshold:
        title = "Revenue is trending up"
    elif change < -threshold:
        title = "Revenue is trending down"
    else:
        title = "Revenue is broadly stable"

    return [
        Insight(
            kind="trend",
            title=title,
            body=(
                f"The second half of the selected period produced "
                f"{format_inr(second_half)} versus {format_inr(first_half)} in the "
                "first half."
            ),
        )
    ]


def _coverage_insight(
    dataframe: pd.DataFrame,
    *,
    order_id_available: bool,
) -> Insight | None:
    if dataframe.empty or "order_date" not in dataframe.columns:
        return None
    dates = pd.to_datetime(dataframe["order_date"], errors="coerce").dropna()
    if dates.empty:
        return None

    orders = count_orders(dataframe, order_id_available=order_id_available)
    order_text = (
        f"{format_number(orders)} orders"
        if order_id_available
        else f"{format_number(orders)} rows (each counted as one order)"
    )
    return Insight(
        kind="coverage",
        title="Selection coverage",
        body=(
            f"{format_number(len(dataframe))} line items · {order_text} · "
            f"{format_date(dates.min().date())} to {format_date(dates.max().date())}."
        ),
    )


def generate_insights(
    dataframe: pd.DataFrame,
    *,
    order_id_available: bool,
    max_items: int = 3,
) -> tuple[Insight, ...]:
    """Create two or three deterministic, data-backed insight statements."""
    if max_items <= 0:
        return ()
    if dataframe.empty:
        return (
            Insight(
                kind="coverage",
                title="No data to summarise",
                body="No rows match the current filters. Reset or widen them to continue.",
            ),
        )

    insights: list[Insight] = [
        *_category_insights(dataframe),
        *_product_insights(dataframe),
        *_trend_insight(dataframe),
    ]
    coverage = _coverage_insight(dataframe, order_id_available=order_id_available)
    if coverage is not None:
        insights.append(coverage)
    return tuple(insights[:max_items])
