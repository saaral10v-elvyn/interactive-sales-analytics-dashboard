import { useRef, useState } from "react";
import type { DragEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { formatBytes, formatNumber } from "../lib/format";
import { useSession } from "../context/session";
import { DownloadButton } from "../components/DownloadButton";
import { Spinner } from "../components/Feedback";

export function HomePage() {
  const { meta, session, startDemo, upload, busy } = useSession();
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  if (!meta) {
    return <Spinner label="Loading app metadata" />;
  }

  async function handleDemo() {
    try {
      await startDemo();
      navigate("/prepare");
    } catch {
      // The shell banner shows the API error.
    }
  }

  async function handleFile(file: File | null) {
    if (!file) return;
    try {
      await upload(file);
      navigate("/prepare");
    } catch {
      // The shell banner shows the API error.
    }
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    void handleFile(event.dataTransfer.files?.[0] ?? null);
  }

  const cleaned = session?.cleaned ?? null;
  const dashboardReady = Boolean(cleaned && !cleaned.report.blocked);

  return (
    <div className="home">
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Sales analytics, end to end</p>
          <h1>Turn a sales CSV into decisions.</h1>
          <p className="hero-lede">{meta.app.tagline}</p>
          <div className="hero-actions">
            <button
              type="button"
              className="button button-primary button-large"
              onClick={() => void handleDemo()}
              disabled={busy}
            >
              {busy ? "Preparing…" : "Explore the demo"}
            </button>
            <button
              type="button"
              className="button button-secondary button-large"
              onClick={() => inputRef.current?.click()}
              disabled={busy}
            >
              Upload a CSV
            </button>
          </div>
          <ul className="hero-points">
            <li>Automatic schema detection with manual overrides</li>
            <li>Validation and cleaning you can inspect, row by row</li>
            <li>KPIs, trends, Pareto analysis and CSV exports</li>
          </ul>
        </div>
        <div className="hero-card" aria-hidden="true">
          <p className="hero-card-label">This dashboard</p>
          <div className="hero-stat">
            <strong>{meta.limits.max_upload_mb} MB</strong>
            <span>max upload</span>
          </div>
          <div className="hero-stat">
            <strong>{formatNumber(meta.limits.max_rows)}</strong>
            <span>row ceiling</span>
          </div>
          <div className="hero-stat">
            <strong>4</strong>
            <span>analytics pages</span>
          </div>
          <p className="hero-card-foot">
            One CSV in. Clean data, charts and exports out — all computed by the
            Python analytics engine.
          </p>
        </div>
      </section>

      {session ? (
        <section className="panel resume-panel">
          <div>
            <p className="eyebrow">Dataset loaded</p>
            <h2>{session.dataset.filename}</h2>
            <p className="muted">
              {formatNumber(session.dataset.row_count)} rows ·{" "}
              {formatBytes(session.dataset.size_bytes)} · revision {session.revision}
            </p>
          </div>
          <div className="resume-actions">
            {dashboardReady && cleaned ? (
              <>
                <span className="status-chip status-chip-ready">
                  Dashboard ready · {formatNumber(cleaned.rows)} cleaned rows
                </span>
                <Link className="button button-primary" to="/overview">
                  Open dashboard
                </Link>
              </>
            ) : cleaned ? (
              <>
                <span className="status-chip">Analysis blocked · review the report</span>
                <Link className="button button-primary" to="/prepare">
                  Review quality report
                </Link>
              </>
            ) : (
              <>
                <span className="status-chip">Preparation in progress</span>
                <Link className="button button-primary" to="/prepare">
                  Continue preparation
                </Link>
              </>
            )}
            {cleaned ? (
              <>
                <DownloadButton kind="cleaned" label="Cleaned CSV" />
                <DownloadButton kind="quality-report" label="Quality report" />
              </>
            ) : null}
          </div>
        </section>
      ) : null}

      <section className="panel upload-panel">
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="visually-hidden"
          onChange={(event) => {
            void handleFile(event.target.files?.[0] ?? null);
            event.target.value = "";
          }}
        />
        <div
          className={dragging ? "dropzone dropzone-active" : "dropzone"}
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              inputRef.current?.click();
            }
          }}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
        >
          <span className="dropzone-mark" aria-hidden="true">
            ⇪
          </span>
          <h2>Drop a sales CSV here</h2>
          <p>
            Or click to browse. Delimiters and encodings are detected
            automatically.
          </p>
          <span className="button button-secondary">Choose a file</span>
          <p className="dropzone-note">
            Up to {meta.limits.max_upload_mb} MB and{" "}
            {formatNumber(meta.limits.max_rows)} rows.{" "}
            {meta.uploads.extensions.join(", ").toUpperCase()} only.
          </p>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Before you upload</p>
            <h2>CSV format guide</h2>
          </div>
          <p className="muted">
            Common aliases such as Date, Qty and Price are detected
            automatically. You can review every match before cleaning.
          </p>
        </div>
        <div className="table-scroll">
          <table className="data-table guide-table">
            <thead>
              <tr>
                <th>Column</th>
                <th>Requirement</th>
                <th>Description</th>
                <th>Example</th>
              </tr>
            </thead>
            <tbody>
              {meta.fields.map((field) => (
                <tr key={field.column}>
                  <td>
                    <code>{field.column}</code>
                  </td>
                  <td>
                    <span
                      className={
                        field.requirement.startsWith("Required")
                          ? "tag tag-required"
                          : field.requirement === "Recommended"
                            ? "tag tag-recommended"
                            : "tag"
                      }
                    >
                      {field.requirement}
                    </span>
                  </td>
                  <td>{field.description}</td>
                  <td className="muted">{field.example}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted small">
          Required*: provide either <code>unit_price</code> or{" "}
          <code>line_total</code>.
        </p>
      </section>
    </div>
  );
}
