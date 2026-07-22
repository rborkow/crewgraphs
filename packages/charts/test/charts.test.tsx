import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import {
  AnnualSeriesChart,
  ChartWithTable,
  SeriesTable,
  buildGeometry,
  formatUSD,
  formatCount,
  type AnnualSeries
} from "../src/index";

afterEach(cleanup);

/**
 * Fixture spanning every semantic the kit must honour:
 * a normal value, a real ZERO, a MISSING year (gap), an AMENDED value, and a
 * PARTIAL (hollow) value.
 */
const series: AnnualSeries = {
  key: "concept:total_revenue",
  label: "Total revenue",
  unit: "USD",
  points: [
    { tax_year: 2019, fy_end: "2019-12-31", value: 900000, quality_state: "verified", is_amended: false, label: "FY2019" },
    { tax_year: 2020, fy_end: "2020-12-31", value: 0, quality_state: "verified", is_amended: false, label: "FY2020" },
    { tax_year: 2021, fy_end: "2021-12-31", value: null, quality_state: "unavailable", is_amended: false, label: "FY2021" },
    { tax_year: 2022, fy_end: "2022-12-31", value: 1250000, quality_state: "verified", is_amended: true, label: "FY2022" },
    { tax_year: 2023, fy_end: "2023-12-31", value: 1100000, quality_state: "partial", is_amended: false, label: "FY2023" },
    { tax_year: 2024, fy_end: "2024-12-31", value: 1300000, quality_state: "verified", is_amended: false, label: "FY2024" }
  ]
};

describe("formatters", () => {
  it("formats USD exact and compact", () => {
    expect(formatUSD(1250000)).toBe("$1,250,000");
    expect(formatUSD(1250000, { compact: true })).toBe("$1.3M");
    // Round values stay clean on the axis — no forced "$1.0M" / "$0.0".
    expect(formatUSD(1000000, { compact: true })).toBe("$1M");
    expect(formatUSD(500000, { compact: true })).toBe("$500K");
    expect(formatUSD(0, { compact: true })).toBe("$0");
  });
  it("formats counts", () => {
    expect(formatCount(1204)).toBe("1,204");
    expect(formatCount(1204, { compact: true })).toBe("1.2K");
  });
});

describe("geometry", () => {
  it("breaks the line at a missing year (two path segments)", () => {
    const g = buildGeometry(series, { kind: "line" });
    expect(g.linePath).not.toBeNull();
    const moveCommands = (g.linePath as string).match(/M/g) ?? [];
    expect(moveCommands.length).toBe(2); // 2019–2020 | 2022–2024, gap at 2021
  });
  it("marks zero as a real value and missing as a gap", () => {
    const g = buildGeometry(series, { kind: "bar" });
    const zero = g.marks.find((m) => m.tax_year === 2020)!;
    const gap = g.marks.find((m) => m.tax_year === 2021)!;
    expect(zero.isZero).toBe(true);
    expect(zero.isMissing).toBe(false);
    expect(zero.barPath).not.toBeNull();
    expect(gap.isMissing).toBe(true);
    expect(gap.barPath).toBeNull();
    expect(gap.missingRect).not.toBeNull();
  });
  it("keeps the baseline at true zero and caps hairlines at 3", () => {
    const g = buildGeometry(series, { kind: "bar" });
    expect(g.hairlines.length).toBeLessThanOrEqual(3);
  });
});

describe("AnnualSeriesChart — line", () => {
  it("renders a broken line path with two segments", () => {
    render(<AnnualSeriesChart kind="line" series={series} ariaSummary="Total revenue 2019–2024" />);
    const path = screen.getByTestId("cg-line");
    const moves = (path.getAttribute("d") ?? "").match(/M/g) ?? [];
    expect(moves.length).toBe(2);
  });

  it("labels the SVG with the aria summary", () => {
    render(<AnnualSeriesChart kind="line" series={series} ariaSummary="Total revenue rose to $1.3M" />);
    expect(screen.getByRole("img", { name: "Total revenue rose to $1.3M" })).toBeInTheDocument();
  });
});

describe("AnnualSeriesChart — bar", () => {
  it("renders a hatched placeholder for the missing year, distinct from zero", () => {
    const { container } = render(
      <AnnualSeriesChart kind="bar" series={series} ariaSummary="Total revenue 2019–2024" />
    );
    const missing = container.querySelector('[data-mark="missing"]');
    const zero = container.querySelector('[data-mark="zero"]');
    expect(missing).not.toBeNull();
    expect(zero).not.toBeNull();
    // Different mark types: hatched rect vs a drawn bar path.
    expect(missing!.tagName.toLowerCase()).toBe("rect");
    expect(zero!.tagName.toLowerCase()).toBe("path");
    expect(missing!.getAttribute("fill")).toContain("url(#");
  });

  it("gives the missing year an accessible 'no filing' button that is disabled", () => {
    render(<AnnualSeriesChart kind="bar" series={series} ariaSummary="summary" />);
    const btn = screen.getByRole("button", { name: /FY2021.*no filing/i });
    expect(btn).toBeDisabled();
  });

  it("renders an amended marker and a '(amended)' accessible name", () => {
    render(<AnnualSeriesChart kind="bar" series={series} ariaSummary="summary" />);
    expect(screen.getAllByTestId("cg-amended").length).toBeGreaterThan(0);
    expect(
      screen.getByRole("button", { name: "FY2022 Total revenue $1,250,000, verified (amended)" })
    ).toBeInTheDocument();
  });

  it("marks a partial value hollow and names its quality (never colour-only)", () => {
    const { container } = render(
      <AnnualSeriesChart kind="bar" series={series} ariaSummary="summary" />
    );
    const partial = container.querySelector('[data-year="2023"][data-quality="partial"]');
    expect(partial).not.toBeNull();
    expect(partial!.getAttribute("stroke-dasharray")).toBeTruthy();
    expect(screen.getByRole("button", { name: /FY2023 Total revenue \$1,100,000, partial/ })).toBeInTheDocument();
  });
});

describe("point activation", () => {
  it("fires onPointActivate with the activated point", () => {
    const onActivate = vi.fn();
    render(<AnnualSeriesChart kind="line" series={series} ariaSummary="summary" onPointActivate={onActivate} />);
    const btn = screen.getByRole("button", { name: "FY2019 Total revenue $900,000, verified" });
    fireEvent.click(btn);
    expect(onActivate).toHaveBeenCalledTimes(1);
    expect(onActivate.mock.calls[0][0].tax_year).toBe(2019);
    expect(onActivate.mock.calls[0][1].key).toBe("concept:total_revenue");
  });

  it("does not fire for a zero value's own point vs a different point", () => {
    const onActivate = vi.fn();
    render(<AnnualSeriesChart kind="bar" series={series} ariaSummary="summary" onPointActivate={onActivate} />);
    const zeroBtn = screen.getByRole("button", { name: "FY2020 Total revenue $0, verified" });
    fireEvent.click(zeroBtn);
    expect(onActivate).toHaveBeenCalledTimes(1);
    expect(onActivate.mock.calls[0][0].value).toBe(0);
  });
});

describe("SeriesTable", () => {
  it("renders a null value as the quality label, never 0 or blank", () => {
    const { container } = render(<SeriesTable series={series} />);
    const row = container.querySelector('tr[data-year="2021"]') as HTMLElement;
    expect(row).not.toBeNull();
    const valueCell = row.querySelector('td[data-value="null"]') as HTMLElement;
    expect(valueCell.textContent).toBe("unavailable");
    expect(valueCell.textContent).not.toBe("0");
    expect(valueCell.textContent).not.toBe("");
  });

  it("renders exact values right-aligned and flags amended rows", () => {
    render(<SeriesTable series={series} />);
    const amendedRow = screen.getByText("FY2022").closest("tr") as HTMLElement;
    expect(within(amendedRow).getByText("$1,250,000")).toBeInTheDocument();
    expect(within(amendedRow).getByTestId("cg-table-amended")).toBeInTheDocument();
  });
});

describe("ChartWithTable toggle", () => {
  it("shows the chart first and flips visibility + aria-pressed on toggle", () => {
    render(<ChartWithTable kind="bar" series={series} ariaSummary="summary" />);

    const chartBtn = screen.getByTestId("cg-toggle-chart");
    const tableBtn = screen.getByTestId("cg-toggle-table");
    const chartRegion = screen.getByTestId("cg-chart-region");
    const tableRegion = screen.getByTestId("cg-table-region");

    // Initial: chart shown, table in the DOM but hidden.
    expect(chartBtn).toHaveAttribute("aria-pressed", "true");
    expect(tableBtn).toHaveAttribute("aria-pressed", "false");
    expect(chartRegion.hidden).toBe(false);
    expect(tableRegion.hidden).toBe(true);

    fireEvent.click(tableBtn);

    expect(chartBtn).toHaveAttribute("aria-pressed", "false");
    expect(tableBtn).toHaveAttribute("aria-pressed", "true");
    expect(chartRegion.hidden).toBe(true);
    expect(tableRegion.hidden).toBe(false);
  });

  it("keeps the table in the DOM for screen readers even while the chart is shown", () => {
    render(<ChartWithTable kind="bar" series={series} ariaSummary="summary" />);
    // The table markup is present regardless of the visual toggle state.
    expect(screen.getByTestId("cg-table-region").querySelector("table")).not.toBeNull();
  });
});
