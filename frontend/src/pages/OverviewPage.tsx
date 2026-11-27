import { useState } from "react";

import type { Granularity, OverviewPayload } from "../api/types";
import { CategoryBarChart, RevenueTrendChart } from "../components/Charts";
import { EmptyState, ErrorBanner, Spinner } from "../components/Feedback";
import { GranularityToggle } from "../components/GranularityToggle";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { useSession } from "../context/session";
import {
  formatDateRange,
  formatInr,
  formatNumber,
  formatShare,
  kpiLabel,
} from "../lib/format";
import { usePagePayload } from "../lib/usePagePayload";

function kpiValue(key: string, value: number): string {
  switch (key) {
    case "total_revenue":
    case "average_order_value":
      return formatInr(value);
    default:
      return formatNumber(value);
  }
}

const INSIGHT_GLYPH: Record<string, string> = {
  category: "◆",
  product: "★",
  trend: "↗",
  coverage: "◔",
};

export function OverviewPage() {
  const { filterSummary } = useSession();
  const { data, loading, error } = usePagePayload<OverviewPayload>("overview");
  const [granularity, setGranularity] = useState<Granularity>("daily");

  if (error && !data) {
    return <ErrorBanner code={error.code} message={error.message} />;
  }
  if (!data) {
    return <Spinner label="Building the overview" />;
  }

  const context = data.context;
  const current = data.kpis.current;
  const isEmpty = context.filtered_rows === 0;
  const maxProduct = Math.max(...data.top_products.map((item) => item.revenue), 1);

  return (
    <div className="stack">
      <PageHeader
        eyebrow="Overview"
        title="Business overview"
        subtitle={
          <>
            {formatDateRange(context.current_period[0], context.current_period[1])}
            {" · "}
            {filterSummary || context.summary}
          </>
        }
        actions={
          <div className="head-chips">
            <span className="chip">
              {formatNumber(context.filtered_rows)} of{" "}
              {formatNumber(context.total_rows)} rows
            </span>
            <span className="chip">
              {context.order_id_available ? "Distinct orders" : "Rows as orders"}
            </span>
            {loading ? <span className="chip chip-live">Updating…</span> : null}
          </div>
        }
      />

      {isEmpty ? (
        <div className="banner banner-warning" role="status">
          <p>
            No rows match the current filters. Widen the date range or clear a
            category, region, product or status selection.
          </p>
        </div>
      ) : null}

      <section className="metric-grid">
        {data.kpis.comparisons.map((comparison) => (
          <MetricCard
            key={comparison.key}
            label={kpiLabel(comparison.key)}
            value={kpiValue(comparison.key, current[comparison.key as keyof typeof current] ?? 0)}
            change={{
              percent: comparison.percent_change,
              available: comparison.previous_available,
            }}
            hint={`Previous: ${kpiValue(comparison.key, comparison.previous)}`}
            accent={comparison.key === "total_revenue"}
          />
        ))}
      </section>

      <section className="panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Revenue over time</p>
            <h2>Trend</h2>
          </div>
          <GranularityToggle value={granularity} onChange={setGranularity} />
        </div>
        <RevenueTrendChart data={data.trend[granularity]} granularity={granularity} />
      </section>

      <div className="split-grid">
        <section className="panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Mix</p>
              <h2>Revenue by category</h2>
            </div>
            <span className="muted small">
              {data.capabilities.has_category
                ? `${data.categories.length} categories`
                : "No category column"}
            </span>
          </div>
          <CategoryBarChart data={data.categories} />
        </section>

        <section className="panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Leaders</p>
              <h2>Top products</h2>
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
                    <div className="rank-track" aria-hidden="true">
                      <span style={{ width: `${(item.revenue / maxProduct) * 100}%` }} />
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

      <section className="panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Signals</p>
            <h2>What stands out</h2>
          </div>
          <span className="muted small">
            {formatShare(
              context.total_rows === 0 ? null : context.filtered_rows / context.total_rows,
            )}{" "}
            of cleaned rows selected
          </span>
        </div>
        {data.insights.length === 0 ? (
          <p className="muted">No insights for this selection.</p>
        ) : (
          <div className="insight-grid">
            {data.insights.map((insight) => (
              <article key={`${insight.kind}-${insight.title}`} className="insight">
                <span className="insight-glyph" aria-hidden="true">
                  {INSIGHT_GLYPH[insight.kind] ?? "•"}
                </span>
                <div>
                  <p className="eyebrow">{insight.kind}</p>
                  <h3>{insight.title}</h3>
                  <p>{insight.body}</p>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
