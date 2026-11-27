import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, api, isAbortError } from "../api/client";
import type {
  CleaningResponse,
  DateFormatDecision,
  DateInspection,
  Row,
} from "../api/types";
import { DownloadButton } from "../components/DownloadButton";
import { ErrorBanner, Spinner } from "../components/Feedback";
import { PageHeader } from "../components/PageHeader";
import { useSession } from "../context/session";
import {
  formatBytes,
  formatNumber,
  titleCase,
} from "../lib/format";

function RequirementTag({ requirement }: { requirement: string }) {
  const tone = requirement.startsWith("Required")
    ? "tag-required"
    : requirement === "Recommended"
      ? "tag-recommended"
      : "";
  return <span className={tone ? `tag ${tone}` : "tag"}>{requirement}</span>;
}

function PreviewTable({ rows }: { rows: Row[] }) {
  if (rows.length === 0) return <p className="table-empty">No preview rows.</p>;
  const columns = Object.keys(rows[0] ?? {});
  return (
    <div className="table-scroll">
      <table className="data-table preview-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column}>{String(row[column] ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function PreparePage() {
  const {
    session,
    sessionId,
    meta,
    busy,
    updateMapping,
    clean,
  } = useSession();
  const [overrides, setOverrides] = useState<Record<string, string | null>>({});
  const [inspection, setInspection] = useState<DateInspection | null>(null);
  const [inspectionLoadedFor, setInspectionLoadedFor] = useState<number | null>(null);
  const [dateFormat, setDateFormat] = useState<DateFormatDecision>("auto");
  const [excludeStatuses, setExcludeStatuses] = useState(true);
  const [decision, setDecision] = useState<DateInspection | null>(null);
  const [result, setResult] = useState<CleaningResponse | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  const dataset = session?.dataset ?? null;
  const mapping = dataset?.mapping ?? null;
  const revision = session?.revision ?? 0;
  const inspectionLoading = inspectionLoadedFor !== revision;

  useEffect(() => {
    if (!sessionId) return;
    const controller = new AbortController();
    api
      .dateInspection(sessionId, controller.signal)
      .then(({ inspection: found }) => {
        setInspection(found);
        if (found && found.ambiguous_count > 0) {
          setDateFormat(
            found.day_first_hint_count >= found.month_first_hint_count ? "DMY" : "MDY",
          );
        } else {
          setDateFormat("auto");
        }
      })
      .catch((caught: unknown) => {
        if (!isAbortError(caught)) {
          setLocalError(
            caught instanceof Error ? caught.message : "Could not inspect dates.",
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setInspectionLoadedFor(revision);
      });
    return () => controller.abort();
  }, [revision, sessionId]);

  if (!session || !dataset || !mapping || !meta) {
    return <Spinner label="Loading dataset" />;
  }

  const cleanedSummary = result?.cleaned ?? session.cleaned;
  const requirementFor = (field: string) =>
    meta.fields.find((item) => item.column === field)?.requirement ?? "Optional";
  const tableRow = (field: string) =>
    mapping.table.find((row) => row.Field === field);

  const selectionFor = (field: string) => {
    if (field in overrides) return overrides[field] ?? "";
    return mapping.fields[field] ?? "";
  };

  const changes: Record<string, string | null> = {};
  for (const field of meta.field_order) {
    const current = mapping.fields[field] ?? "";
    const next = selectionFor(field);
    if (next !== current) changes[field] = next === "" ? null : next;
  }
  const hasChanges = Object.keys(changes).length > 0;

  async function handleSaveMapping() {
    setLocalError(null);
    setResult(null);
    try {
      await updateMapping(changes);
      setOverrides({});
    } catch (caught) {
      setLocalError(caught instanceof Error ? caught.message : "Mapping failed.");
    }
  }

  async function handleClean(forced?: DateFormatDecision) {
    setLocalError(null);
    setDecision(null);
    try {
      const response = await clean({
        date_format: forced ?? dateFormat,
        exclude_statuses: excludeStatuses,
      });
      setResult(response);
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === "DATE_DECISION_REQUIRED") {
        const details = caught.details as { inspection?: DateInspection } | null;
        const found = details?.inspection ?? inspection;
        setDecision(found);
        if (found) {
          setInspection(found);
          if (found.suggested_format === "DMY" || found.suggested_format === "MDY") {
            setDateFormat(found.suggested_format);
          }
        }
      } else if (caught instanceof ApiError) {
        setLocalError(caught.message);
      }
    }
  }

  return (
    <div className="stack">
      <PageHeader
        eyebrow="Preparation"
        title="Review and clean"
        subtitle={
          <>
            {dataset.filename} · {formatNumber(dataset.row_count)} rows ·{" "}
            {dataset.column_count} columns · {formatBytes(dataset.size_bytes)}
          </>
        }
        actions={
          cleanedSummary && !cleanedSummary.report.blocked ? (
            <Link className="button button-primary" to="/overview">
              Open dashboard
            </Link>
          ) : null
        }
      />

      {localError ? (
        <ErrorBanner message={localError} onDismiss={() => setLocalError(null)} />
      ) : null}

      {dataset.warnings.length > 0 ? (
        <div className="banner banner-warning" role="status">
          <div>
            <strong>Load warnings</strong>
            <ul>
              {dataset.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}

      <section className="panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Step 1</p>
            <h2>Column mapping</h2>
          </div>
          <p className="muted">
            Detected automatically from headers and content. Change a source
            column if a match is wrong, then save.
          </p>
        </div>

        <div className="table-scroll">
          <table className="data-table mapping-table">
            <thead>
              <tr>
                <th>Field</th>
                <th>Requirement</th>
                <th>Source column</th>
                <th>Detected</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {meta.field_order.map((field) => {
                const row = tableRow(field);
                const selected = selectionFor(field);
                return (
                  <tr key={field}>
                    <td>
                      <code>{meta.field_labels[field] ?? field}</code>
                    </td>
                    <td>
                      <RequirementTag requirement={requirementFor(field)} />
                    </td>
                    <td>
                      <select
                        value={selected}
                        onChange={(event) =>
                          setOverrides((current) => ({
                            ...current,
                            [field]: event.target.value || null,
                          }))
                        }
                      >
                        <option value="">Not mapped</option>
                        {dataset.columns.map((column) => (
                          <option key={column} value={column}>
                            {column}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="muted">
                      {row ? `${row.Method} · ${row.Confidence}` : "—"}
                    </td>
                    <td>
                      <span
                        className={
                          row?.Status === "Missing"
                            ? "tag tag-required"
                            : row?.Status === "Review"
                              ? "tag tag-recommended"
                              : "tag tag-ready"
                        }
                      >
                        {row?.Status ?? "Missing"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="panel-actions">
          <span className="muted small">
            {mapping.is_complete
              ? "All required columns are mapped."
              : `Missing: ${mapping.missing_required.join(", ") || "required columns"}`}
          </span>
          <button
            type="button"
            className="button button-secondary"
            onClick={() => void handleSaveMapping()}
            disabled={!hasChanges || busy}
          >
            {hasChanges ? `Save ${Object.keys(changes).length} change(s)` : "No changes"}
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Step 2</p>
            <h2>Dates and cleaning</h2>
          </div>
          <p className="muted">
            Cleaning validates types, normalises labels and removes unusable
            rows. The quality report records every action.
          </p>
        </div>

        {inspectionLoading ? (
          <Spinner label="Inspecting the date column" />
        ) : inspection ? (
          <div className="inspection-grid">
            <div className="inspection-stat">
              <span>Values</span>
              <strong>{formatNumber(inspection.total_values)}</strong>
            </div>
            <div className="inspection-stat">
              <span>Parseable</span>
              <strong>{formatNumber(inspection.parseable_count)}</strong>
            </div>
            <div className="inspection-stat">
              <span>Invalid</span>
              <strong>{formatNumber(inspection.invalid_count)}</strong>
            </div>
            <div className="inspection-stat">
              <span>Ambiguous</span>
              <strong>{formatNumber(inspection.ambiguous_count)}</strong>
            </div>
          </div>
        ) : (
          <p className="muted">
            No date column is mapped, so the dashboard will be unavailable.
          </p>
        )}

        {inspection && inspection.ambiguous_count > 0 ? (
          <div className="decision-box">
            <div>
              <h3>Day-first or month-first?</h3>
              <p className="muted">
                {formatNumber(inspection.ambiguous_count)} values could be read
                either way, for example{" "}
                {inspection.ambiguous_examples.slice(0, 3).join(", ")}. Choose a
                format before cleaning.
              </p>
            </div>
            <div className="radio-row">
              {(["DMY", "MDY"] as DateFormatDecision[]).map((format) => (
                <label key={format} className="radio-card">
                  <input
                    type="radio"
                    name="date-format"
                    value={format}
                    checked={dateFormat === format}
                    onChange={() => setDateFormat(format)}
                  />
                  <span>
                    <strong>{format}</strong>
                    <small>
                      {format === "DMY" ? "31/01/2026 is 31 Jan" : "01/31/2026 is 31 Jan"}
                    </small>
                  </span>
                </label>
              ))}
            </div>
          </div>
        ) : null}

        <div className="clean-actions">
          <label className="check-row">
            <input
              type="checkbox"
              checked={excludeStatuses}
              onChange={(event) => setExcludeStatuses(event.target.checked)}
            />
            <span>
              Exclude cancelled, returned and failed orders
              <small className="muted block">
                Returns stay available as negative quantities only when this is
                unchecked.
              </small>
            </span>
          </label>
          <button
            type="button"
            className="button button-primary"
            onClick={() => void handleClean()}
            disabled={busy || !mapping.is_complete}
          >
            {busy ? "Cleaning…" : "Clean dataset"}
          </button>
        </div>

        {decision ? (
          <div className="banner banner-warning" role="alert">
            <p>
              The server needs a date decision before cleaning. Choose DMY or
              MDY above, then run cleaning again.
            </p>
            <button
              type="button"
              className="button button-secondary"
              onClick={() => void handleClean(dateFormat)}
            >
              Clean with {dateFormat}
            </button>
          </div>
        ) : null}
      </section>

      {cleanedSummary ? (
        <section className="panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Step 3</p>
              <h2>Quality report</h2>
            </div>
            <div className="inline-actions">
              <DownloadButton kind="cleaned" label="Download cleaned CSV" />
              <DownloadButton kind="quality-report" label="Download quality report" />
            </div>
          </div>

          {cleanedSummary.report.blocked ? (
            <div className="banner banner-error" role="alert">
              <p>
                Analysis blocked:{" "}
                {cleanedSummary.report.block_reason ??
                  "the dataset has no usable rows."}
              </p>
            </div>
          ) : null}

          <div className="report-grid">
            <div className="inspection-stat">
              <span>Rows in</span>
              <strong>{formatNumber(cleanedSummary.report.rows_input)}</strong>
            </div>
            <div className="inspection-stat">
              <span>Usable rows</span>
              <strong>{formatNumber(cleanedSummary.report.rows_output)}</strong>
            </div>
            <div className="inspection-stat">
              <span>Rows removed</span>
              <strong>
                {formatNumber(cleanedSummary.report.rows_dropped)} (
                {(cleanedSummary.report.dropped_ratio * 100).toFixed(1)}%)
              </strong>
            </div>
            <div className="inspection-stat">
              <span>Returns kept</span>
              <strong>{formatNumber(cleanedSummary.returns_kept)}</strong>
            </div>
            <div className="inspection-stat">
              <span>Revenue source</span>
              <strong className="capitalize">{cleanedSummary.revenue_source}</strong>
            </div>
            <div className="inspection-stat">
              <span>Date format</span>
              <strong>{cleanedSummary.date_format_used ?? "auto"}</strong>
            </div>
          </div>

          {cleanedSummary.report.issues.length > 0 ? (
            <ul className="issue-list">
              {cleanedSummary.report.issues.map((issue) => (
                <li key={issue.code} className={`issue issue-${issue.severity}`}>
                  <div className="issue-head">
                    <span className={`tag tag-${issue.severity}`}>
                      {titleCase(issue.severity)}
                    </span>
                    <strong>{issue.description}</strong>
                    <span className="muted small">{issue.affected_label}</span>
                  </div>
                  <p>{issue.action_taken}</p>
                  {issue.example_text ? (
                    <p className="muted small">Examples: {issue.example_text}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No issues were reported.</p>
          )}

          <div className="panel-head">
            <h3>Cleaned preview</h3>
            <span className="muted small">
              {formatNumber(cleanedSummary.rows)} rows ·{" "}
              {cleanedSummary.columns.length} columns
            </span>
          </div>
          <PreviewTable rows={cleanedSummary.preview} />
        </section>
      ) : (
        <section className="panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Preview</p>
              <h2>First rows of the uploaded file</h2>
            </div>
            <span className="muted small">Before cleaning</span>
          </div>
          <PreviewTable rows={dataset.preview} />
        </section>
      )}
    </div>
  );
}
