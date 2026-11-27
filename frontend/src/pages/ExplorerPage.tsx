import { useEffect, useState } from "react";

import type { ExplorerPayload } from "../api/types";
import { DownloadButton } from "../components/DownloadButton";
import { EmptyState, ErrorBanner, Spinner } from "../components/Feedback";
import { PageHeader } from "../components/PageHeader";
import { useSession } from "../context/session";
import {
  formatDate,
  formatInr,
  formatNumber,
} from "../lib/format";
import { usePagePayload } from "../lib/usePagePayload";

const LIMITS = [10, 25, 50, 100, 250, 500];

function renderCell(column: string, value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  if (column === "order_date") return formatDate(String(value));
  if (typeof value === "number") {
    return Number.isInteger(value) ? formatNumber(value) : formatNumber(value, 2);
  }
  return String(value);
}

export function ExplorerPage() {
  const { filterState, filterSummary } = useSession();
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [limit, setLimit] = useState(25);
  const [hiddenColumns, setHiddenColumns] = useState<Set<string>>(new Set());
  const { data, loading, error } = usePagePayload<ExplorerPayload>("explorer", {
    search: debounced,
    limit,
  });

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  if (error && !data) {
    return <ErrorBanner code={error.code} message={error.message} />;
  }
  if (!data) {
    return <Spinner label="Loading the data explorer" />;
  }

  const filterBody = { ...(filterState ?? {}), search: debounced };
  const noMatches = data.matching_rows === 0;
  const columns = data.columns;
  const visibleColumns = columns.filter((column) => !hiddenColumns.has(column));

  function toggleColumn(column: string) {
    setHiddenColumns((current) => {
      const next = new Set(current);
      if (next.has(column)) next.delete(column);
      else next.add(column);
      return next;
    });
  }

  return (
    <div className="stack">
      <PageHeader
        eyebrow="Data Explorer"
        title="Inspect the cleaned rows"
        subtitle={
          <>
            {formatNumber(data.filtered_rows)} filtered rows ·{" "}
            {filterSummary || data.context.summary}
          </>
        }
        actions={
          <div className="head-chips">
            <span className="chip">{formatNumber(data.matching_rows)} matching</span>
            <span className="chip">{formatNumber(data.rows_shown)} shown</span>
            {loading ? <span className="chip chip-live">Updating…</span> : null}
          </div>
        }
      />

      <section className="panel explorer-controls">
        <label className="search-field">
          <span className="visually-hidden">Search rows</span>
          <span className="search-icon" aria-hidden="true">
            ⌕
          </span>
          <input
            type="search"
            value={search}
            placeholder="Search products, regions, order IDs or dates"
            onChange={(event) => setSearch(event.target.value)}
          />
          {search ? (
            <button
              type="button"
              className="icon-button"
              onClick={() => setSearch("")}
              aria-label="Clear search"
            >
              ×
            </button>
          ) : null}
        </label>

        <label className="field field-inline">
          <span>Rows</span>
          <select
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value))}
          >
            {LIMITS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>

        <details className="multiselect column-picker">
          <summary>
            <span>Columns</span>
            <span className="multiselect-count">
              {visibleColumns.length}/{columns.length}
            </span>
          </summary>
          <div className="multiselect-panel">
            <div className="multiselect-head">
              <span>Preview columns</span>
              {hiddenColumns.size > 0 ? (
                <button
                  type="button"
                  className="link-button"
                  onClick={() => setHiddenColumns(new Set())}
                >
                  Show all
                </button>
              ) : null}
            </div>
            {columns.map((column) => (
              <label key={column} className="check-row">
                <input
                  type="checkbox"
                  checked={!hiddenColumns.has(column)}
                  onChange={() => toggleColumn(column)}
                />
                <span>{column}</span>
              </label>
            ))}
          </div>
        </details>

        <div className="download-row">
          <DownloadButton
            kind="filtered"
            label="Filtered CSV"
            body={filterBody}
            variant="primary"
            disabled={data.matching_rows === 0}
          />
          <DownloadButton kind="cleaned" label="Cleaned CSV" />
          <DownloadButton kind="quality-report" label="Quality report" />
        </div>
      </section>

      <section className="metric-grid metric-grid-compact">
        <div className="metric-card">
          <p className="metric-label">Filtered rows</p>
          <p className="metric-value">{formatNumber(data.filtered_rows)}</p>
          <p className="metric-hint">of {formatNumber(data.context.total_rows)} cleaned</p>
        </div>
        <div className="metric-card">
          <p className="metric-label">Matching rows</p>
          <p className="metric-value">{formatNumber(data.matching_rows)}</p>
          <p className="metric-hint">{debounced ? "After search" : "No search applied"}</p>
        </div>
        <div className="metric-card">
          <p className="metric-label">Rows shown</p>
          <p className="metric-value">{formatNumber(data.rows_shown)}</p>
          <p className="metric-hint">Limit {limit}</p>
        </div>
        <div className="metric-card">
          <p className="metric-label">Filtered revenue</p>
          <p className="metric-value">{formatInr(data.filtered_revenue, { compact: true })}</p>
          <p className="metric-hint">Net revenue in matching rows</p>
        </div>
      </section>

      {noMatches ? (
        <div className="banner banner-warning" role="status">
          <p>
            No rows match{debounced ? ` “${debounced}”` : " the current filters"}.
            Clear the search or widen the filter selection.
          </p>
        </div>
      ) : null}

      <section className="panel panel-flush">
        {noMatches ? (
          <EmptyState title="Nothing to show">
            <p>Try a different search term or widen the filters.</p>
          </EmptyState>
        ) : visibleColumns.length === 0 ? (
          <EmptyState title="No columns selected">
            <p>Choose at least one column to preview the matching rows.</p>
          </EmptyState>
        ) : (
          <div className="table-scroll table-scroll-tall">
            <table className="data-table explorer-table">
              <thead>
                <tr>
                  {visibleColumns.map((column) => (
                    <th key={column}>{column}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.preview.map((row, index) => (
                  <tr key={index}>
                    {visibleColumns.map((column) => (
                      <td
                        key={column}
                        className={
                          typeof row[column] === "number" ? "num" : undefined
                        }
                      >
                        {renderCell(column, row[column])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
