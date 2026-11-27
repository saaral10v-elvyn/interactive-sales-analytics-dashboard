/**
 * Display formatting. Presentation only: no business rules live here.
 *
 * The rupee helpers mirror `sales_dashboard.formatting` so the React app shows
 * the same Indian grouping and lakh/crore shorthand as the original interface.
 */

import type { Granularity } from "../api/types";

export const CURRENCY_SYMBOL = "₹";

function asNumber(value: number | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  if (!Number.isFinite(value)) return null;
  return value;
}

function groupIndian(digits: string): string {
  if (digits.length <= 3) return digits;
  const tail = digits.slice(-3);
  let head = digits.slice(0, -3);
  const groups: string[] = [];
  while (head.length > 2) {
    groups.unshift(head.slice(-2));
    head = head.slice(0, -2);
  }
  if (head) groups.unshift(head);
  return [...groups, tail].join(",");
}

export function formatNumber(value: number | null | undefined, decimals = 0): string {
  const numeric = asNumber(value);
  if (numeric === null) return "—";
  const rounded = Math.abs(numeric).toFixed(decimals);
  const [integer, fraction] = rounded.split(".");
  const grouped = groupIndian(integer ?? "0");
  const sign = numeric < 0 ? "-" : "";
  return decimals && fraction ? `${sign}${grouped}.${fraction}` : `${sign}${grouped}`;
}

export function formatInr(
  value: number | null | undefined,
  options: { compact?: boolean; decimals?: number } = {},
): string {
  const { compact = false, decimals = 0 } = options;
  const numeric = asNumber(value);
  if (numeric === null) return "—";

  const sign = numeric < 0 ? "-" : "";
  const absolute = Math.abs(numeric);

  if (compact) {
    if (absolute >= 10_000_000) {
      return `${sign}${CURRENCY_SYMBOL}${(absolute / 10_000_000).toFixed(2)} Cr`;
    }
    if (absolute >= 100_000) {
      return `${sign}${CURRENCY_SYMBOL}${(absolute / 100_000).toFixed(2)} L`;
    }
    if (absolute >= 1_000) {
      return `${sign}${CURRENCY_SYMBOL}${(absolute / 1_000).toFixed(1)} K`;
    }
  }

  return `${sign}${CURRENCY_SYMBOL}${formatNumber(absolute, decimals)}`;
}

/** Format a ratio (0.365) as a percentage string. */
export function formatShare(value: number | null | undefined, decimals = 1): string {
  const numeric = asNumber(value);
  if (numeric === null) return "—";
  return `${(numeric * 100).toFixed(decimals)}%`;
}

/** Format a percentage number that is already scaled (27.55 -> "+27.5%"). */
export function formatChange(percent: number | null | undefined, decimals = 1): string {
  const numeric = asNumber(percent);
  if (numeric === null) return "—";
  const sign = numeric > 0 ? "+" : "";
  return `${sign}${numeric.toFixed(decimals)}%`;
}

export function formatSignedInr(value: number | null | undefined): string {
  const numeric = asNumber(value);
  if (numeric === null) return "—";
  const sign = numeric > 0 ? "+" : numeric < 0 ? "-" : "";
  return `${sign}${formatInr(Math.abs(numeric), { compact: true })}`;
}

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

function parseDate(value: string): Date | null {
  const date = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** Format `2026-08-03` or an ISO timestamp as `03 Aug 2026`. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = parseDate(value);
  if (!date) return value;
  return `${String(date.getDate()).padStart(2, "0")} ${MONTHS[date.getMonth()]} ${date.getFullYear()}`;
}

export function formatDateRange(
  start: string | null | undefined,
  end: string | null | undefined,
): string {
  if (!start && !end) return "—";
  if (!start) return `Until ${formatDate(end)}`;
  if (!end) return `From ${formatDate(start)}`;
  return `${formatDate(start)} – ${formatDate(end)}`;
}

export function formatTrendLabel(period: string, granularity: Granularity): string {
  const date = parseDate(period);
  if (!date) return period;
  if (granularity === "monthly") {
    return `${MONTHS[date.getMonth()]} ${date.getFullYear()}`;
  }
  return `${String(date.getDate()).padStart(2, "0")} ${MONTHS[date.getMonth()]}`;
}

export function formatBytes(size: number | null | undefined): string {
  const numeric = asNumber(size);
  if (numeric === null || numeric < 0) return "—";
  if (numeric < 1024) return `${Math.round(numeric)} B`;
  if (numeric < 1024 ** 2) return `${(numeric / 1024).toFixed(1)} KB`;
  return `${(numeric / 1024 ** 2).toFixed(1)} MB`;
}

export function pluralize(count: number, singular: string, plural?: string): string {
  return count === 1 ? singular : (plural ?? `${singular}s`);
}

export function titleCase(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function kpiLabel(key: string): string {
  const labels: Record<string, string> = {
    total_revenue: "Total revenue",
    total_orders: "Total orders",
    average_order_value: "Average order value",
    total_units: "Units sold",
    total_products: "Products sold",
  };
  return labels[key] ?? titleCase(key);
}
