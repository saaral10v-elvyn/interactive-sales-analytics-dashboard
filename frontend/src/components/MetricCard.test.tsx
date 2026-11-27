import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MetricCard } from "./MetricCard";

describe("MetricCard", () => {
  it("shows the value, the change and the previous value", () => {
    render(
      <MetricCard
        label="Total revenue"
        value="₹51,65,861"
        change={{ percent: 27.546, available: true }}
        hint="Previous: ₹40,50,182"
        accent
      />,
    );

    expect(screen.getByText("Total revenue")).toBeInTheDocument();
    expect(screen.getByText("₹51,65,861")).toBeInTheDocument();
    expect(screen.getByText("+27.5%")).toBeInTheDocument();
    expect(screen.getByText("Previous: ₹40,50,182")).toBeInTheDocument();
  });

  it("marks a falling metric", () => {
    render(
      <MetricCard
        label="Units sold"
        value="1,470"
        change={{ percent: -12.5, available: true }}
      />,
    );

    expect(screen.getByText("-12.5%")).toBeInTheDocument();
    expect(screen.getByText("-12.5%")).toHaveClass("metric-change-down");
  });

  it("explains when there is no previous period", () => {
    render(
      <MetricCard
        label="Total products"
        value="0"
        change={{ percent: null, available: false }}
      />,
    );

    expect(screen.getByText("No previous period")).toBeInTheDocument();
  });
});
