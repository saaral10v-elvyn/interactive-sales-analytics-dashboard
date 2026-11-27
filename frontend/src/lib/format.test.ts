import { describe, expect, it } from "vitest";

import {
  formatBytes,
  formatChange,
  formatDate,
  formatDateRange,
  formatInr,
  formatNumber,
  formatShare,
  formatSignedInr,
  formatTrendLabel,
  kpiLabel,
  pluralize,
  titleCase,
} from "./format";

describe("formatNumber", () => {
  it("groups digits the Indian way", () => {
    expect(formatNumber(1234567)).toBe("12,34,567");
    expect(formatNumber(123456789)).toBe("12,34,56,789");
    expect(formatNumber(999)).toBe("999");
    expect(formatNumber(1000)).toBe("1,000");
  });

  it("keeps decimals and signs", () => {
    expect(formatNumber(1234.567, 2)).toBe("1,234.57");
    expect(formatNumber(-1234)).toBe("-1,234");
    expect(formatNumber(0)).toBe("0");
  });

  it("renders missing values as an em dash", () => {
    expect(formatNumber(null)).toBe("—");
    expect(formatNumber(Number.NaN)).toBe("—");
    expect(formatNumber(Number.POSITIVE_INFINITY)).toBe("—");
  });
});

describe("formatInr", () => {
  it("prefixes the rupee symbol", () => {
    expect(formatInr(5165861.05)).toBe("₹51,65,861");
    expect(formatInr(10629.343724)).toBe("₹10,629");
  });

  it("uses lakh and crore shorthand when compact", () => {
    expect(formatInr(5165861, { compact: true })).toBe("₹51.66 L");
    expect(formatInr(12500000, { compact: true })).toBe("₹1.25 Cr");
    expect(formatInr(1500, { compact: true })).toBe("₹1.5 K");
    expect(formatInr(-250000, { compact: true })).toBe("-₹2.50 L");
  });

  it("falls back to full rupees below a thousand", () => {
    expect(formatInr(950, { compact: true })).toBe("₹950");
    expect(formatInr(null)).toBe("—");
  });
});

describe("percentages", () => {
  it("scales shares to percentages", () => {
    expect(formatShare(0.143053)).toBe("14.3%");
    expect(formatShare(1)).toBe("100.0%");
    expect(formatShare(null)).toBe("—");
  });

  it("keeps the sign on changes", () => {
    expect(formatChange(27.54639)).toBe("+27.5%");
    expect(formatChange(-4.2)).toBe("-4.2%");
    expect(formatChange(0)).toBe("0.0%");
    expect(formatChange(null)).toBe("—");
    expect(formatSignedInr(1115678.95)).toBe("+₹11.16 L");
    expect(formatSignedInr(-5000)).toBe("-₹5.0 K");
  });
});

describe("dates", () => {
  it("formats dates the way the Python helpers do", () => {
    expect(formatDate("2026-08-03")).toBe("03 Aug 2026");
    expect(formatDate("2026-10-31T00:00:00")).toBe("31 Oct 2026");
    expect(formatDate(null)).toBe("—");
  });

  it("formats date ranges", () => {
    expect(formatDateRange("2026-08-03", "2026-10-31")).toBe("03 Aug 2026 – 31 Oct 2026");
    expect(formatDateRange(null, "2026-10-31")).toBe("Until 31 Oct 2026");
    expect(formatDateRange("2026-08-03", null)).toBe("From 03 Aug 2026");
    expect(formatDateRange(null, null)).toBe("—");
  });

  it("labels trend buckets by granularity", () => {
    expect(formatTrendLabel("2026-08-03T00:00:00", "daily")).toBe("03 Aug");
    expect(formatTrendLabel("2026-08-01T00:00:00", "monthly")).toBe("Aug 2026");
    expect(formatTrendLabel("not-a-date", "weekly")).toBe("not-a-date");
  });
});

describe("miscellaneous formatting", () => {
  it("scales file sizes", () => {
    expect(formatBytes(474)).toBe("474 B");
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(474281)).toBe("463.2 KB");
    expect(formatBytes(2.5 * 1024 ** 2)).toBe("2.5 MB");
    expect(formatBytes(-1)).toBe("—");
  });

  it("pluralises and title-cases labels", () => {
    expect(pluralize(1, "row")).toBe("row");
    expect(pluralize(2, "row")).toBe("rows");
    expect(titleCase("average_order_value")).toBe("Average Order Value");
    expect(kpiLabel("total_revenue")).toBe("Total revenue");
    expect(kpiLabel("unknown_metric")).toBe("Unknown Metric");
  });
});
