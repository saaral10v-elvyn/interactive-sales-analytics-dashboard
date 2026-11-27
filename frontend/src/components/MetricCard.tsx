import type { ReactNode } from "react";

import { formatChange } from "../lib/format";

export interface MetricCardProps {
  label: string;
  value: string;
  hint?: ReactNode;
  change?: {
    percent: number | null;
    available: boolean;
  };
  accent?: boolean;
}

export function MetricCard({ label, value, hint, change, accent = false }: MetricCardProps) {
  const direction =
    change?.available && change.percent !== null
      ? change.percent > 0
        ? "up"
        : change.percent < 0
          ? "down"
          : "flat"
      : null;

  return (
    <article className={accent ? "metric-card metric-card-accent" : "metric-card"}>
      <p className="metric-label">{label}</p>
      <p className="metric-value">{value}</p>
      <div className="metric-meta">
        {change?.available ? (
          <span className={`metric-change metric-change-${direction ?? "flat"}`}>
            <span aria-hidden="true">
              {direction === "up" ? "▲" : direction === "down" ? "▼" : "■"}
            </span>{" "}
            {formatChange(change.percent)}
          </span>
        ) : (
          <span className="metric-change metric-change-muted">No previous period</span>
        )}
        {hint ? <span className="metric-hint">{hint}</span> : null}
      </div>
    </article>
  );
}
