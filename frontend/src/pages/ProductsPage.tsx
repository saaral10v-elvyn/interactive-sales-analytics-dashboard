import { useState } from "react";

import type { Granularity, ProductPerformanceRow, ProductsPayload } from "../api/types";
import { ParetoChart, RevenueTrendChart } from "../components/Charts";
import { DataTable } from "../components/DataTable";
import type { Column } from "../components/DataTable";
import { EmptyState, ErrorBanner, Spinner } from "../components/Feedback";
import { GranularityToggle } from "../components/GranularityToggle";
import { PageHeader } from "../components/PageHeader";
import { useSession } from "../context/session";
import {
  formatDateRange,
  formatInr,
  formatNumber,
  formatShare,
} from "../lib/format";
import { usePagePayload } from "../lib/usePagePayload";

const COLUMNS: Column<ProductPerformanceRow>[] = [
  {
    key: "product",
    header: "Product",
    render: (row) => <strong>{row.product}</strong>,
    sortValue: (row) => row.product,
  },
  {
    key: "revenue",
    header: "Revenue",
    align: "right",
    render: (row) => formatInr(row.revenue),
    sortValue: (row) => row.revenue,
  },
  {
    key: "units",
    header: "Units",
    align: "right",
    render: (row) => formatNumber(row.units),
    sortValue: (row) => row.units,
  },
  {
    key: "orders",
    header: "Orders",
    align: "right",
    render: (row) => formatNumber(row.orders),
    sortValue: (row) => row.orders,
  },
  {
    key: "average_order_value",
    header: "Avg order",
    align: "right",
    render: (row) => formatInr(row.average_order_value),
    sortValue: (row) => row.average_order_value,
  },
  {
    key: "share",
    header: "Share",
    align: "right",
    render: (row) => formatShare(row.share),
    sortValue: (row) => row.share ?? -1,
  },
];

export function ProductsPage() {
  const { filterSummary } = useSession();
  const { data, loading, error } = usePagePayload<ProductsPayload>("products");
  const [granularity, setGranularity] = useState<Granularity>("daily");

  if (error && !data) {
    return <ErrorBanner code={error.code} message={error.message} />;
  }
  if (!data) {
    return <Spinner label="Loading product performance" />;
  }

  const context = data.context;
  const snapshot = data.drilldown?.snapshot ?? null;
  const empty = context.filtered_rows === 0;

  return (
    <div className="stack">
      <PageHeader
        eyebrow="Products"
        title="Product performance"
        subtitle={
          <>
            {formatDateRange(context.current_period[0], context.current_period[1])}
            {" · "}
            {filterSummary || context.summary}
          </>
        }
        actions={
          <div className="head-chips">
            <span className="chip">{formatNumber(data.performance.length)} products</span>
            <span className="chip">{formatNumber(context.filtered_rows)} rows</span>
            {loading ? <span className="chip chip-live">Updating…</span> : null}
          </div>
        }
      />

      {empty ? (
        <div className="banner banner-warning" role="status">
          <p>No products match the current filters.</p>
        </div>
      ) : null}

      <div className="split-grid split-grid-wide">
        <section className="panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Concentration</p>
              <h2>Pareto analysis</h2>
            </div>
            {data.threshold ? (
              <span className="chip">
                Threshold: {data.threshold.product}
              </span>
            ) : null}
          </div>
          <ParetoChart data={data.pareto} />
          {data.notes.pareto_unavailable ? (
            <p className="muted small">
              {data.notes.pareto_unavailable === "empty_selection"
                ? "Pareto is unavailable because the selection has no rows."
                : "Pareto is unavailable because no product has positive revenue."}
            </p>
          ) : data.threshold ? (
            <p className="muted small">
              The first {formatNumber(data.threshold.rank)} products reach{" "}
              {formatShare(data.threshold.cumulative_share)} of revenue;{" "}
              <strong>{data.threshold.product}</strong> is the last one needed to
              cross 80%.
            </p>
          ) : null}
        </section>

        <section className="panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Top of the list</p>
              <h2>Top 10 products</h2>
            </div>
          </div>
          {data.top_products.length === 0 ? (
            <EmptyState title="No product revenue in this range" />
          ) : (
            <ol className="rank-list">
              {data.top_products.map((item, index) => (
                <li key={item.product}>
                  <span className="rank-index">{index + 1}</span>
                  <div className="rank-body">
                    <div className="rank-head">
                      <span>{item.product}</span>
                      <span className="num">{formatInr(item.revenue)}</span>
                    </div>
                    <span className="muted small">
                      {formatNumber(item.units)} units
                    </span>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>

      {data.drilldown ? (
        <section className="panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Drill-down</p>
              <h2>{data.drilldown.product}</h2>
            </div>
            <GranularityToggle value={granularity} onChange={setGranularity} />
          </div>

          <div className="metric-grid metric-grid-compact">
            <div className="metric-card">
              <p className="metric-label">Revenue</p>
              <p className="metric-value">{formatInr(snapshot?.total_revenue ?? 0)}</p>
            </div>
            <div className="metric-card">
              <p className="metric-label">Orders</p>
              <p className="metric-value">{formatNumber(snapshot?.total_orders ?? 0)}</p>
            </div>
            <div className="metric-card">
              <p className="metric-label">Units</p>
              <p className="metric-value">{formatNumber(snapshot?.total_units ?? 0)}</p>
            </div>
            <div className="metric-card">
              <p className="metric-label">Avg order</p>
              <p className="metric-value">
                {formatInr(snapshot?.average_order_value ?? 0)}
              </p>
            </div>
          </div>

          <RevenueTrendChart
            data={data.drilldown.trend[granularity]}
            granularity={granularity}
          />
        </section>
      ) : (
        <section className="panel">
          <EmptyState title="No drill-down available">
            <p>Select a period with product revenue to see the trend.</p>
          </EmptyState>
        </section>
      )}

      <section className="panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Full table</p>
            <h2>Every product</h2>
          </div>
          {data.notes.share_unavailable ? (
            <span className="muted small">
              Revenue share is unavailable because orders could not be counted.
            </span>
          ) : null}
        </div>
        <DataTable
          columns={COLUMNS}
          rows={data.performance}
          rowKey={(row) => row.product}
          initialSort={{ key: "revenue", direction: "desc" }}
          emptyMessage="No products in this selection."
        />
      </section>
    </div>
  );
}
