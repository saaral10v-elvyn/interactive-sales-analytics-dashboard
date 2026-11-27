import { useState } from "react";

import type { Granularity, RegionPerformanceRow, RegionsPayload } from "../api/types";
import { CategoryMixChart, RegionTrendChart } from "../components/Charts";
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

const COLUMNS: Column<RegionPerformanceRow>[] = [
  {
    key: "region",
    header: "Region",
    render: (row) => <strong>{row.region || "Unspecified"}</strong>,
    sortValue: (row) => row.region,
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

export function RegionsPage() {
  const { filterSummary } = useSession();
  const { data, loading, error } = usePagePayload<RegionsPayload>("regions");
  const [granularity, setGranularity] = useState<Granularity>("daily");

  if (error && !data) {
    return <ErrorBanner code={error.code} message={error.message} />;
  }
  if (!data) {
    return <Spinner label="Loading regional performance" />;
  }

  const context = data.context;
  const regions = data.performance.map((row) => row.region).filter(Boolean);
  const categories = [
    ...new Set(data.category_mix.map((row) => row.category).filter(Boolean)),
  ].sort((left, right) => left.localeCompare(right));

  return (
    <div className="stack">
      <PageHeader
        eyebrow="Regions"
        title="Regional performance"
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
              {data.available ? `${formatNumber(regions.length)} regions` : "No region column"}
            </span>
            <span className="chip">{formatNumber(context.filtered_rows)} rows</span>
            {loading ? <span className="chip chip-live">Updating…</span> : null}
          </div>
        }
      />

      {!data.available ? (
        <div className="banner banner-warning" role="status">
          <p>
            This dataset has no <code>region</code> column, so regional
            comparisons are unavailable. You can still explore the other pages.
          </p>
        </div>
      ) : null}

      {data.blank_region_rows > 0 ? (
        <div className="banner banner-warning" role="status">
          <p>
            {formatNumber(data.blank_region_rows)} cleaned rows have a blank
            region and appear as <strong>Unspecified</strong>.
          </p>
        </div>
      ) : null}

      {data.available ? (
        <>
          <div className="split-grid split-grid-wide">
            <section className="panel">
              <div className="panel-head">
                <div>
                  <p className="eyebrow">Mix</p>
                  <h2>Revenue by region and category</h2>
                </div>
                <span className="muted small">
                  {data.has_category ? `${categories.length} categories` : "No category column"}
                </span>
              </div>
              <CategoryMixChart
                data={data.category_mix}
                regions={regions}
                categories={categories}
              />
            </section>

            <section className="panel">
              <div className="panel-head">
                <div>
                  <p className="eyebrow">Over time</p>
                  <h2>Regional trend</h2>
                </div>
                <GranularityToggle value={granularity} onChange={setGranularity} />
              </div>
              <RegionTrendChart
                data={data.trend[granularity]}
                regions={regions}
                granularity={granularity}
              />
            </section>
          </div>

          <section className="panel">
            <div className="panel-head">
              <div>
                <p className="eyebrow">Full table</p>
                <h2>Every region</h2>
              </div>
            </div>
            <DataTable
              columns={COLUMNS}
              rows={data.performance}
              rowKey={(row) => row.region || "unspecified"}
              initialSort={{ key: "revenue", direction: "desc" }}
              emptyMessage="No regional revenue in this selection."
            />
          </section>
        </>
      ) : (
        <section className="panel">
          <EmptyState title="Regional analysis unavailable">
            <p>
              Map a region column during preparation to unlock this page.
            </p>
          </EmptyState>
        </section>
      )}
    </div>
  );
}
