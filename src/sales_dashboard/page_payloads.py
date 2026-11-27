"""Page payload builders shared by the API and the parity fixtures.

Each function turns a cleaned dataset plus a resolved filter state into the
JSON body the React frontend renders. Nothing here touches a web framework, a
chart library or HTTP: the same functions build ``tests/golden`` and answer
``POST /api/datasets/{id}/{page}``, so the frontend and the fixtures cannot
drift apart.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from sales_dashboard.analytics import (
    KPI_KEYS,
    category_revenue,
    compute_dashboard_metrics,
    generate_insights,
    pareto_threshold,
    product_pareto,
    product_performance,
    product_revenue_trend,
    product_snapshot,
    region_category_revenue,
    regional_performance,
    regional_revenue_trend,
    revenue_trend,
    top_products,
)
from sales_dashboard.explorer import search_dataframe
from sales_dashboard.filters import apply_filters, summarize_filters
from sales_dashboard.models import CleanedDataset, FilterState
from sales_dashboard.payloads import filter_state_dict, jsonable, records

#: Rows shown in the explorer preview when the caller does not choose a limit.
DEFAULT_EXPLORER_LIMIT = 25

#: Upper bound accepted for the explorer preview.
MAX_EXPLORER_LIMIT = 500


def _context(cleaned: CleanedDataset, state: FilterState, filtered: pd.DataFrame) -> dict[str, Any]:
    """Describe the selection every page header shares."""
    metrics = compute_dashboard_metrics(
        cleaned.dataframe,
        state,
        order_id_available=cleaned.order_id_available,
    )
    return {
        "filters": filter_state_dict(state),
        "summary": summarize_filters(state),
        "filtered_rows": len(filtered),
        "total_rows": len(cleaned.dataframe),
        "current_period": list(metrics.current_period),
        "previous_period": list(metrics.previous_period),
        "previous_rows": metrics.previous_rows,
        "order_id_available": cleaned.order_id_available,
    }


def overview_payload(cleaned: CleanedDataset, state: FilterState) -> dict[str, Any]:
    """Build the Overview page: KPIs, trend, breakdowns and insights."""
    dataframe = cleaned.dataframe
    filtered = apply_filters(dataframe, state)
    metrics = compute_dashboard_metrics(
        dataframe,
        state,
        order_id_available=cleaned.order_id_available,
    )

    comparisons = [
        {
            "key": comparison.key,
            "current": comparison.current,
            "previous": comparison.previous,
            "absolute_change": comparison.absolute_change,
            "percent_change": comparison.percent_change,
            "previous_available": comparison.previous_available,
        }
        for comparison in metrics.comparisons
    ]
    assert [item["key"] for item in comparisons] == list(KPI_KEYS)

    return {
        "context": _context(cleaned, state, filtered),
        "kpis": {
            "current": {
                "total_revenue": metrics.current.total_revenue,
                "total_orders": metrics.current.total_orders,
                "average_order_value": metrics.current.average_order_value,
                "total_units": metrics.current.total_units,
                "total_products": metrics.current.total_products,
                "rows": metrics.current.rows,
            },
            "previous": {
                "total_revenue": metrics.previous.total_revenue,
                "total_orders": metrics.previous.total_orders,
                "average_order_value": metrics.previous.average_order_value,
                "total_units": metrics.previous.total_units,
                "total_products": metrics.previous.total_products,
                "rows": metrics.previous.rows,
            },
            "comparisons": comparisons,
        },
        "trend": {
            granularity: records(
                revenue_trend(
                    filtered,
                    granularity,  # type: ignore[arg-type]
                    order_id_available=cleaned.order_id_available,
                )
            )
            for granularity in ("daily", "weekly", "monthly")
        },
        "categories": records(category_revenue(filtered)),
        "top_products": records(
            top_products(
                filtered,
                limit=10,
                order_id_available=cleaned.order_id_available,
            )
        ),
        "insights": [
            {"kind": insight.kind, "title": insight.title, "body": insight.body}
            for insight in generate_insights(
                filtered,
                order_id_available=cleaned.order_id_available,
                max_items=3,
            )
        ],
        "capabilities": {
            "has_category": "category" in dataframe.columns,
            "has_region": "region" in dataframe.columns,
            "has_dates": "order_date" in dataframe.columns,
            "order_id_available": cleaned.order_id_available,
        },
    }


def products_payload(cleaned: CleanedDataset, state: FilterState) -> dict[str, Any]:
    """Build the Products page: table, ranking, Pareto and drill-down."""
    dataframe = cleaned.dataframe
    filtered = apply_filters(dataframe, state)
    performance = product_performance(
        filtered,
        order_id_available=cleaned.order_id_available,
    )
    pareto = product_pareto(filtered, order_id_available=cleaned.order_id_available)
    threshold = pareto_threshold(pareto)

    drilldown: dict[str, Any] | None = None
    if not performance.empty:
        product = str(performance["product"].iloc[0])
        snapshot = product_snapshot(
            filtered,
            product,
            order_id_available=cleaned.order_id_available,
        )
        drilldown = {
            "product": product,
            "snapshot": {
                "total_revenue": snapshot.total_revenue,
                "total_orders": snapshot.total_orders,
                "total_units": snapshot.total_units,
                "average_order_value": snapshot.average_order_value,
                "rows": snapshot.rows,
            },
            "trend": {
                granularity: records(
                    product_revenue_trend(
                        filtered,
                        product,
                        granularity,  # type: ignore[arg-type]
                        order_id_available=cleaned.order_id_available,
                    )
                )
                for granularity in ("daily", "weekly", "monthly")
            },
        }

    if filtered.empty:
        pareto_unavailable = "empty_selection"
    elif pareto.empty:
        pareto_unavailable = "no_positive_revenue"
    else:
        pareto_unavailable = None

    return {
        "context": _context(cleaned, state, filtered),
        "performance": records(performance),
        "top_products": records(
            top_products(
                filtered,
                limit=10,
                order_id_available=cleaned.order_id_available,
            )
        ),
        "pareto": records(pareto),
        "threshold": jsonable(threshold),
        "drilldown": drilldown,
        "notes": {
            "share_unavailable": bool(not performance.empty and performance["share"].isna().all()),
            "pareto_unavailable": pareto_unavailable,
        },
    }


def regions_payload(cleaned: CleanedDataset, state: FilterState) -> dict[str, Any]:
    """Build the Regions page: table, mix and multi-line trend."""
    dataframe = cleaned.dataframe
    filtered = apply_filters(dataframe, state)
    available = "region" in dataframe.columns
    performance = regional_performance(
        filtered,
        order_id_available=cleaned.order_id_available,
    )

    blank_regions = 0
    if available and "region" in filtered.columns:
        labels = filtered["region"].astype("string").str.strip()
        blank_regions = int((labels.eq("") | labels.isna()).sum())

    return {
        "context": _context(cleaned, state, filtered),
        "available": available,
        "has_category": "category" in dataframe.columns,
        "performance": records(performance),
        "category_mix": records(region_category_revenue(filtered)),
        "trend": {
            granularity: records(
                regional_revenue_trend(
                    filtered,
                    granularity,  # type: ignore[arg-type]
                )
            )
            for granularity in ("daily", "weekly", "monthly")
        },
        "blank_region_rows": blank_regions,
    }


def explorer_payload(
    cleaned: CleanedDataset,
    state: FilterState,
    *,
    search: str | None = None,
    limit: int = DEFAULT_EXPLORER_LIMIT,
) -> dict[str, Any]:
    """Build the Data Explorer: counts, search results and a preview slice.

    ``search=None`` picks a stable term from the data itself, which is what the
    frozen fixtures record. An explicit ``""`` means no search at all.
    """
    dataframe = cleaned.dataframe
    filtered = apply_filters(dataframe, state)
    columns = [str(column) for column in dataframe.columns]
    term = _search_term(filtered) if search is None else search
    searched = search_dataframe(filtered, term)

    revenue = 0.0
    if not searched.empty and "revenue" in searched.columns:
        revenue = float(pd.to_numeric(searched["revenue"], errors="coerce").sum())

    return {
        "context": _context(cleaned, state, filtered),
        "columns": columns,
        "search_term": term,
        "filtered_rows": len(filtered),
        "matching_rows": len(searched),
        "rows_shown": min(limit, len(searched)),
        "filtered_revenue": revenue,
        "preview": records(searched.head(limit)),
    }


def _search_term(dataframe: pd.DataFrame) -> str:
    """Pick a stable, realistic search term from the data itself."""
    for column in ("product", "category", "region", "status"):
        if column not in dataframe.columns or dataframe.empty:
            continue
        values = dataframe[column].astype("string").str.strip()
        usable = values[values.ne("") & values.notna()].drop_duplicates().sort_values()
        if not usable.empty:
            return str(usable.iloc[0])
    return ""
