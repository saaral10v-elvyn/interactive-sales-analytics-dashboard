import { useMemo } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type {
  CategoryRevenue,
  Granularity,
  ParetoRow,
  RegionCategoryRow,
  RegionTrendPoint,
  TrendPoint,
} from "../api/types";
import { EmptyState } from "./Feedback";
import {
  formatDate,
  formatInr,
  formatShare,
  formatTrendLabel,
  titleCase,
} from "../lib/format";

const CHART_COLORS = [
  "#4f46e5",
  "#0ea5e9",
  "#f59e0b",
  "#10b981",
  "#ef4444",
  "#8b5cf6",
  "#64748b",
  "#ec4899",
];

const AXIS = { fontSize: 12, fill: "#64748b" };
const TOOLTIP_STYLE = {
  borderRadius: 12,
  border: "1px solid #e2e8f0",
  boxShadow: "0 12px 30px rgba(15, 23, 42, 0.12)",
  fontSize: 12,
};

export function RevenueTrendChart({
  data,
  granularity,
}: {
  data: TrendPoint[];
  granularity: Granularity;
}) {
  if (data.length === 0) {
    return <EmptyState title="No revenue in this range" />;
  }
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={290}>
        <AreaChart data={data} margin={{ top: 12, right: 12, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="revenue-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#4f46e5" stopOpacity={0.32} />
              <stop offset="100%" stopColor="#4f46e5" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
          <XAxis
            dataKey="period"
            tickLine={false}
            axisLine={false}
            minTickGap={28}
            tick={AXIS}
            tickFormatter={(value) => formatTrendLabel(String(value), granularity)}
          />
          <YAxis
            width={74}
            tickLine={false}
            axisLine={false}
            tick={AXIS}
            tickFormatter={(value) => formatInr(Number(value), { compact: true })}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            labelFormatter={(value) => formatDate(String(value))}
            formatter={(value) => [formatInr(Number(value)), "Revenue"]}
          />
          <Area
            type="monotone"
            dataKey="revenue"
            name="Revenue"
            stroke="#4f46e5"
            strokeWidth={2.4}
            fill="url(#revenue-fill)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function CategoryBarChart({ data }: { data: CategoryRevenue[] }) {
  if (data.length === 0) {
    return <EmptyState title="No category revenue in this range" />;
  }
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={Math.max(220, data.length * 42)}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 28, bottom: 0, left: 4 }}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
          <XAxis
            type="number"
            tickLine={false}
            axisLine={false}
            tick={AXIS}
            tickFormatter={(value) => formatInr(Number(value), { compact: true })}
          />
          <YAxis
            type="category"
            dataKey="category"
            width={126}
            tickLine={false}
            axisLine={false}
            tick={AXIS}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            formatter={(value, _name, item) => [
              formatInr(Number(value)),
              `${item?.payload?.category ?? "Category"} · ${formatShare(item?.payload?.share)}`,
            ]}
          />
          <Bar dataKey="revenue" name="Revenue" fill="#4f46e5" radius={[0, 6, 6, 0]} barSize={18} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ParetoChart({ data }: { data: ParetoRow[] }) {
  if (data.length === 0) {
    return (
      <EmptyState title="Pareto analysis is unavailable">
        <p>No product in this selection has positive revenue.</p>
      </EmptyState>
    );
  }

  const series = data.map((row) => ({
    ...row,
    share_percent: row.cumulative_share * 100,
  }));

  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={series} margin={{ top: 12, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
          <XAxis
            dataKey="rank"
            tickLine={false}
            axisLine={false}
            tick={AXIS}
            tickFormatter={(value) => `#${value}`}
          />
          <YAxis
            yAxisId="revenue"
            width={74}
            tickLine={false}
            axisLine={false}
            tick={AXIS}
            tickFormatter={(value) => formatInr(Number(value), { compact: true })}
          />
          <YAxis
            yAxisId="share"
            orientation="right"
            domain={[0, 100]}
            width={46}
            tickLine={false}
            axisLine={false}
            tick={AXIS}
            tickFormatter={(value) => `${Number(value)}%`}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            labelFormatter={(value) => `Rank ${value}`}
            formatter={(value, name) =>
              name === "Cumulative share"
                ? [`${Number(value).toFixed(1)}%`, name]
                : [formatInr(Number(value)), name]
            }
          />
          <Bar
            yAxisId="revenue"
            dataKey="revenue"
            name="Revenue"
            fill="#c7d2fe"
            radius={[4, 4, 0, 0]}
          />
          <Line
            yAxisId="share"
            type="monotone"
            dataKey="share_percent"
            name="Cumulative share"
            stroke="#4f46e5"
            strokeWidth={2.4}
            dot={false}
          />
          <ReferenceLine
            yAxisId="share"
            y={80}
            stroke="#f59e0b"
            strokeDasharray="5 4"
            label={{ value: "80%", position: "insideTopRight", fill: "#b45309", fontSize: 11 }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function CategoryMixChart({
  data,
  regions,
  categories,
}: {
  data: RegionCategoryRow[];
  regions: string[];
  categories: string[];
}) {
  const rows = useMemo(
    () =>
      regions.map((region) => {
        const row: Record<string, string | number> = { region };
        for (const category of categories) row[category] = 0;
        for (const entry of data) {
          if (entry.region === region) row[entry.category] = entry.revenue;
        }
        return row;
      }),
    [categories, data, regions],
  );

  if (rows.length === 0 || categories.length === 0) {
    return (
      <EmptyState title="No category mix available">
        <p>Add a category column to compare regions by category.</p>
      </EmptyState>
    );
  }

  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={Math.max(260, rows.length * 52)}>
        <BarChart
          data={rows}
          layout="vertical"
          margin={{ top: 4, right: 20, bottom: 0, left: 4 }}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
          <XAxis
            type="number"
            tickLine={false}
            axisLine={false}
            tick={AXIS}
            tickFormatter={(value) => formatInr(Number(value), { compact: true })}
          />
          <YAxis
            type="category"
            dataKey="region"
            width={94}
            tickLine={false}
            axisLine={false}
            tick={AXIS}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            formatter={(value, name) => [formatInr(Number(value)), titleCase(String(name))]}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {categories.map((category, index) => (
            <Bar
              key={category}
              dataKey={category}
              stackId="mix"
              fill={CHART_COLORS[index % CHART_COLORS.length]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function RegionTrendChart({
  data,
  regions,
  granularity,
}: {
  data: RegionTrendPoint[];
  regions: string[];
  granularity: Granularity;
}) {
  const rows = useMemo(() => {
    const byPeriod = new Map<string, Record<string, string | number>>();
    for (const point of data) {
      const row = byPeriod.get(point.period) ?? { period: point.period };
      row[point.region] = point.revenue;
      byPeriod.set(point.period, row);
    }
    return [...byPeriod.values()].sort((left, right) =>
      String(left.period).localeCompare(String(right.period)),
    );
  }, [data]);

  if (rows.length === 0 || regions.length === 0) {
    return <EmptyState title="No regional revenue in this range" />;
  }

  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={rows} margin={{ top: 12, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
          <XAxis
            dataKey="period"
            tickLine={false}
            axisLine={false}
            minTickGap={28}
            tick={AXIS}
            tickFormatter={(value) => formatTrendLabel(String(value), granularity)}
          />
          <YAxis
            width={74}
            tickLine={false}
            axisLine={false}
            tick={AXIS}
            tickFormatter={(value) => formatInr(Number(value), { compact: true })}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            labelFormatter={(value) => formatDate(String(value))}
            formatter={(value, name) => [formatInr(Number(value)), String(name)]}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {regions.map((region, index) => (
            <Line
              key={region}
              type="monotone"
              dataKey={region}
              stroke={CHART_COLORS[index % CHART_COLORS.length]}
              strokeWidth={2}
              dot={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
