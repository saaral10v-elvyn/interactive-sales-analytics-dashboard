"""Plotly figures for the Overview dashboard.

The builders accept tidy dataframes from :mod:`sales_dashboard.analytics` and
return figures with consistent INR formatting, tooltips and zoom/pan support.
They contain no data logic, which keeps the analytics layer testable on its own.
"""

from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go

from sales_dashboard.config import (
    ACCENT_COLOR,
    BRAND_COLOR,
    SLATE_200,
    SLATE_600,
    SLATE_900,
)
from sales_dashboard.formatting import format_inr, format_number
from sales_dashboard.models import ParetoThreshold, TrendGranularity

CHART_PALETTE: tuple[str, ...] = (
    "#0F766E",
    "#14B8A6",
    "#0EA5E9",
    "#6366F1",
    "#F59E0B",
    "#EC4899",
    "#64748B",
    "#84CC16",
)

PLOTLY_CONFIG: dict[str, object] = {
    "displaylogo": False,
    "scrollZoom": True,
    "responsive": True,
}
_GRANULARITY_HOVER = {
    "daily": "%d %b %Y",
    "weekly": "Week of %d %b %Y",
    "monthly": "%b %Y",
}
_GRANULARITY_TICK = {
    "daily": "%d %b",
    "weekly": "%d %b",
    "monthly": "%b %Y",
}
_MAX_X_TICKS = 9


def date_axis_range(periods: pd.Series, granularity: TrendGranularity) -> list[pd.Timestamp] | None:
    """Pad a date axis so edge markers and ticks are not clipped."""
    values = pd.to_datetime(pd.Series(periods), errors="coerce").dropna()
    if values.empty:
        return None
    padding = {
        "daily": pd.Timedelta(hours=12),
        "weekly": pd.Timedelta(days=3, hours=12),
        "monthly": pd.Timedelta(days=15),
    }[granularity]
    return [values.min() - padding, values.max() + padding]


def date_tick_values(
    periods: pd.Series, granularity: TrendGranularity
) -> tuple[list[pd.Timestamp], list[str]]:
    """Choose evenly spaced, uniquely labelled ticks for a date axis.

    Plotly's automatic date ticks can repeat the same month label when the axis
    spans a few months. Explicit ticks keep the axis readable for daily, weekly
    and monthly trends with any number of periods.
    """
    values = (
        pd.to_datetime(pd.Series(periods), errors="coerce").dropna().drop_duplicates().sort_values()
    )
    if values.empty:
        return [], []

    if len(values) > _MAX_X_TICKS:
        step = math.ceil(len(values) / _MAX_X_TICKS)
        values = values.iloc[::step]

    date_format = _GRANULARITY_TICK.get(granularity, "%Y-%m-%d")
    ticks = values.tolist()
    return ticks, [timestamp.strftime(date_format) for timestamp in ticks]


def _nice_number(value: float) -> float:
    """Round a value up to a friendly 1/2/2.5/5/10 step."""
    if value <= 0 or not math.isfinite(value):
        return 1.0
    exponent = math.floor(math.log10(value))
    magnitude = 10.0**exponent
    residual = value / magnitude
    for step in (1.0, 2.0, 2.5, 5.0, 10.0):
        if residual <= step:
            return step * magnitude
    return 10.0 * magnitude


def inr_axis_ticks(values: pd.Series | list[float]) -> tuple[list[float], list[str], list[float]]:
    """Return tick values, Indian-formatted labels and a padded axis range."""
    finite = [float(value) for value in values if pd.notna(value) and math.isfinite(float(value))]
    if not finite:
        finite = [0.0]

    low = min(0.0, min(finite))
    high = max(0.0, max(finite))
    if low == high:
        high = low + 1.0

    step = _nice_number((high - low) / 5)
    start = math.floor(low / step) * step
    end = math.ceil(high / step) * step
    if end <= start:
        end = start + step

    ticks: list[float] = []
    value = start
    for _ in range(40):
        ticks.append(value)
        if value >= end - step * 1e-9:
            break
        value += step
    if ticks[-1] < high:
        ticks.append(end)

    labels = [format_inr(tick, compact=True) for tick in ticks]
    return ticks, labels, [start, end]


def _apply_base_layout(
    figure: go.Figure,
    *,
    title: str,
    x_title: str,
    y_title: str,
    height: int,
) -> None:
    figure.update_layout(
        template="plotly_white",
        title={
            "text": title,
            "x": 0,
            "xanchor": "left",
            "font": {"size": 17, "color": SLATE_900},
        },
        margin={"l": 8, "r": 12, "t": 54, "b": 8},
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "sans-serif", "color": SLATE_600, "size": 12},
        hoverlabel={
            "bgcolor": "#FFFFFF",
            "bordercolor": SLATE_200,
            "font": {"color": SLATE_900, "size": 12},
        },
        dragmode="zoom",
        hovermode="closest",
    )
    figure.update_xaxes(
        title_text=x_title,
        showgrid=False,
        linecolor=SLATE_200,
        tickfont={"color": SLATE_600},
    )
    figure.update_yaxes(
        title_text=y_title,
        gridcolor=SLATE_200,
        zeroline=False,
        tickfont={"color": SLATE_600},
    )


def build_revenue_trend_figure(
    trend: pd.DataFrame,
    granularity: TrendGranularity,
    *,
    title: str = "Revenue trend",
) -> go.Figure | None:
    """Build the revenue trend line chart."""
    if trend.empty:
        return None

    hover_date = _GRANULARITY_HOVER[granularity]
    custom = list(
        zip(
            [format_inr(value) for value in trend["revenue"]],
            [format_number(value) for value in trend["orders"]],
            [format_number(value) for value in trend["units"]],
            strict=False,
        )
    )

    figure = go.Figure(
        go.Scatter(
            x=trend["period"],
            y=trend["revenue"],
            mode="lines+markers",
            name="Revenue",
            line={"color": BRAND_COLOR, "width": 2.6},
            marker={"size": 6, "color": BRAND_COLOR},
            fill="tozeroy",
            fillcolor="rgba(15, 118, 110, 0.08)",
            customdata=custom,
            hovertemplate=(
                f"%{{x|{hover_date}}}<br>"
                "Revenue: %{customdata[0]}<br>"
                "Orders: %{customdata[1]}<br>"
                "Units: %{customdata[2]}<extra></extra>"
            ),
        )
    )

    tickvals, ticktext, axis_range = inr_axis_ticks(trend["revenue"])
    x_tickvals, x_ticktext = date_tick_values(trend["period"], granularity)
    _apply_base_layout(
        figure,
        title=title,
        x_title="Period",
        y_title="Revenue (INR)",
        height=390,
    )
    figure.update_xaxes(
        tickmode="array",
        tickvals=x_tickvals,
        ticktext=x_ticktext,
        range=date_axis_range(trend["period"], granularity),
    )
    figure.update_yaxes(
        tickvals=tickvals,
        ticktext=ticktext,
        range=axis_range,
    )
    return figure


def build_category_figure(data: pd.DataFrame) -> go.Figure | None:
    """Build the revenue-by-category bar chart."""
    if data.empty:
        return None

    colors = [CHART_PALETTE[index % len(CHART_PALETTE)] for index in range(len(data))]
    custom = list(
        zip(
            [f"{float(share):.1%}" if share else "—" for share in data["share"]],
            [format_inr(value) for value in data["revenue"]],
            [format_number(value) for value in data["units"]],
            strict=False,
        )
    )

    figure = go.Figure(
        go.Bar(
            x=data["category"],
            y=data["revenue"],
            marker_color=colors,
            marker_line_width=0,
            customdata=custom,
            hovertemplate=(
                "%{x}<br>"
                "Revenue: %{customdata[1]}<br>"
                "Share: %{customdata[0]}<br>"
                "Units: %{customdata[2]}<extra></extra>"
            ),
        )
    )

    tickvals, ticktext, axis_range = inr_axis_ticks(data["revenue"])
    _apply_base_layout(
        figure,
        title="Revenue by category",
        x_title="Category",
        y_title="Revenue (INR)",
        height=390,
    )
    figure.update_xaxes(tickangle=-20)
    figure.update_yaxes(
        tickvals=tickvals,
        ticktext=ticktext,
        range=axis_range,
    )
    return figure


def build_top_products_figure(data: pd.DataFrame) -> go.Figure | None:
    """Build the top-10 products horizontal bar chart."""
    if data.empty:
        return None

    # Reverse so the highest-revenue product appears at the top of the chart.
    plot_data = data.iloc[::-1]
    custom = list(
        zip(
            [format_inr(value) for value in plot_data["revenue"]],
            [format_number(value) for value in plot_data["units"]],
            strict=False,
        )
    )
    height = max(340, 36 * len(plot_data) + 110)

    figure = go.Figure(
        go.Bar(
            x=plot_data["revenue"],
            y=plot_data["product"],
            orientation="h",
            marker_color=ACCENT_COLOR,
            marker_line_width=0,
            customdata=custom,
            hovertemplate=(
                "%{y}<br>Revenue: %{customdata[0]}<br>Units: %{customdata[1]}<extra></extra>"
            ),
        )
    )

    tickvals, ticktext, axis_range = inr_axis_ticks(plot_data["revenue"])
    _apply_base_layout(
        figure,
        title="Top products by revenue",
        x_title="Revenue (INR)",
        y_title="Product",
        height=height,
    )
    figure.update_xaxes(
        tickvals=tickvals,
        ticktext=ticktext,
        range=axis_range,
    )
    figure.update_yaxes(tickfont={"size": 11})
    return figure


def build_product_pareto_figure(
    data: pd.DataFrame,
    threshold: ParetoThreshold | None,
) -> go.Figure | None:
    """Build revenue bars with a cumulative-share line and the 80% marker."""
    if data.empty:
        return None

    custom = list(
        zip(
            [format_inr(value) for value in data["revenue"]],
            [format_number(value) for value in data["rank"]],
            [f"{float(value):.1%}" for value in data["cumulative_share"]],
            strict=False,
        )
    )

    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=data["product"],
            y=data["revenue"],
            name="Revenue",
            marker_color=ACCENT_COLOR,
            marker_line_width=0,
            customdata=custom,
            hovertemplate=(
                "%{x}<br>Revenue: %{customdata[0]}<br>"
                "Rank: %{customdata[1]}<br>"
                "Cumulative: %{customdata[2]}<extra></extra>"
            ),
        )
    )
    figure.add_trace(
        go.Scatter(
            x=data["product"],
            y=data["cumulative_share"] * 100.0,
            mode="lines+markers",
            name="Cumulative share",
            yaxis="y2",
            line={"color": BRAND_COLOR, "width": 2.2},
            marker={"size": 6, "color": BRAND_COLOR},
            hovertemplate="%{x}<br>Cumulative: %{y:.1f}%<extra></extra>",
        )
    )

    if threshold is not None:
        figure.add_trace(
            go.Scatter(
                x=[threshold.product],
                y=[threshold.cumulative_share * 100.0],
                mode="markers",
                name="80% threshold",
                yaxis="y2",
                marker={"size": 12, "color": "#F59E0B", "line": {"width": 2, "color": "#FFFFFF"}},
                hovertemplate=(
                    f"%{{x}}<br>Cumulative: %{{y:.1f}}%<br>Rank {threshold.rank}<extra></extra>"
                ),
            )
        )
        figure.add_shape(
            type="line",
            xref="paper",
            x0=0,
            x1=1,
            yref="y2",
            y0=80,
            y1=80,
            line={"color": SLATE_600, "width": 1, "dash": "dash"},
        )
        figure.add_annotation(
            xref="paper",
            x=1,
            yref="y2",
            y=80,
            text=f"80% threshold · {threshold.product}",
            showarrow=False,
            xanchor="right",
            yshift=12,
            font={"size": 11, "color": SLATE_600},
        )

    tickvals, ticktext, axis_range = inr_axis_ticks(data["revenue"])
    _apply_base_layout(
        figure,
        title="Pareto analysis: revenue concentration",
        x_title="Product (ranked by revenue)",
        y_title="Revenue (INR)",
        height=430,
    )
    figure.update_xaxes(tickangle=-35)
    figure.update_yaxes(
        tickvals=tickvals,
        ticktext=ticktext,
        range=axis_range,
    )
    figure.update_layout(
        bargap=0.25,
        yaxis2={
            "title": {"text": "Cumulative revenue share"},
            "overlaying": "y",
            "side": "right",
            "range": [0, 105],
            "ticksuffix": "%",
            "showgrid": False,
            "zeroline": False,
            "tickfont": {"color": SLATE_600},
        },
    )
    return figure


def build_region_revenue_figure(data: pd.DataFrame) -> go.Figure | None:
    """Build a horizontal revenue-by-region bar chart."""
    if data.empty:
        return None

    plot_data = data.iloc[::-1]
    custom = list(
        zip(
            [format_inr(value) for value in plot_data["revenue"]],
            [format_number(value) for value in plot_data["orders"]],
            [format_number(value) for value in plot_data["units"]],
            [f"{float(value):.1%}" if value == value else "—" for value in plot_data["share"]],
            strict=False,
        )
    )
    height = max(300, 42 * len(plot_data) + 110)

    figure = go.Figure(
        go.Bar(
            x=plot_data["revenue"],
            y=plot_data["region"],
            orientation="h",
            marker_color=BRAND_COLOR,
            marker_line_width=0,
            customdata=custom,
            hovertemplate=(
                "%{y}<br>Revenue: %{customdata[0]}<br>"
                "Orders: %{customdata[1]}<br>Units: %{customdata[2]}<br>"
                "Share: %{customdata[3]}<extra></extra>"
            ),
        )
    )

    tickvals, ticktext, axis_range = inr_axis_ticks(plot_data["revenue"])
    _apply_base_layout(
        figure,
        title="Revenue by region",
        x_title="Revenue (INR)",
        y_title="Region",
        height=height,
    )
    figure.update_xaxes(
        tickvals=tickvals,
        ticktext=ticktext,
        range=axis_range,
    )
    figure.update_yaxes(tickfont={"size": 11})
    return figure


def build_region_category_figure(data: pd.DataFrame) -> go.Figure | None:
    """Build a stacked category-by-region revenue chart."""
    if data.empty:
        return None

    region_order = (
        data.groupby("region")["revenue"].sum().sort_values(ascending=False, kind="stable").index
    )
    category_order = (
        data.groupby("category")["revenue"].sum().sort_values(ascending=False, kind="stable").index
    )

    figure = go.Figure()
    for index, category in enumerate(category_order):
        subset = (
            data.loc[data["category"] == category]
            .set_index("region")
            .reindex(region_order)["revenue"]
            .fillna(0.0)
        )
        figure.add_trace(
            go.Bar(
                x=list(region_order),
                y=list(subset),
                name=str(category),
                marker_color=CHART_PALETTE[index % len(CHART_PALETTE)],
                marker_line_width=0,
                customdata=[format_inr(value) for value in subset],
                hovertemplate=(
                    f"{category}<br>Region: %{{x}}<br>Revenue: %{{customdata}}<extra></extra>"
                ),
            )
        )

    tickvals, ticktext, axis_range = inr_axis_ticks(data["revenue"])
    _apply_base_layout(
        figure,
        title="Category revenue by region",
        x_title="Region",
        y_title="Revenue (INR)",
        height=430,
    )
    figure.update_xaxes(tickangle=-20)
    figure.update_yaxes(
        tickvals=tickvals,
        ticktext=ticktext,
        range=axis_range,
    )
    figure.update_layout(
        barmode="stack",
        bargap=0.3,
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.18,
            "xanchor": "left",
            "x": 0,
            "font": {"size": 11},
        },
        margin={"b": 95},
    )
    return figure


def build_regional_trend_figure(
    data: pd.DataFrame,
    granularity: TrendGranularity,
) -> go.Figure | None:
    """Build a multi-line regional revenue trend."""
    if data.empty:
        return None

    hover_date = _GRANULARITY_HOVER[granularity]
    region_order = (
        data.groupby("region")["revenue"].sum().sort_values(ascending=False, kind="stable").index
    )

    figure = go.Figure()
    for index, region in enumerate(region_order):
        subset = data.loc[data["region"] == region]
        figure.add_trace(
            go.Scatter(
                x=subset["period"],
                y=subset["revenue"],
                mode="lines+markers",
                name=str(region),
                line={"color": CHART_PALETTE[index % len(CHART_PALETTE)], "width": 2.2},
                marker={"size": 5},
                customdata=[format_inr(value) for value in subset["revenue"]],
                hovertemplate=(
                    f"%{{x|{hover_date}}}<br>{region}<br>Revenue: %{{customdata}}<extra></extra>"
                ),
            )
        )

    tickvals, ticktext, axis_range = inr_axis_ticks(data["revenue"])
    x_tickvals, x_ticktext = date_tick_values(data["period"], granularity)
    _apply_base_layout(
        figure,
        title="Regional revenue trend",
        x_title="Period",
        y_title="Revenue (INR)",
        height=390,
    )
    figure.update_xaxes(
        tickmode="array",
        tickvals=x_tickvals,
        ticktext=x_ticktext,
        range=date_axis_range(data["period"], granularity),
    )
    figure.update_yaxes(
        tickvals=tickvals,
        ticktext=ticktext,
        range=axis_range,
    )
    figure.update_layout(
        hovermode="x unified",
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
            "font": {"size": 11},
        },
    )
    return figure
