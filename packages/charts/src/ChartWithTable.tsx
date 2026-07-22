"use client";

import { useId, useState } from "react";
import { ChartPlot } from "./ChartPlot";
import { SeriesTable } from "./SeriesTable";
import type { AnnualSeries, ChartKind, PointActivateHandler } from "./types";

export interface ChartWithTableProps {
  kind: ChartKind;
  series: AnnualSeries;
  ariaSummary: string;
  height?: number;
  width?: number;
  initialView?: "chart" | "table";
  onPointActivate?: PointActivateHandler;
}

const C = {
  ink: "var(--color-river, #0E1B2C)",
  paper: "var(--color-paper, #F7F9FB)",
  hairline: "var(--color-hairline, #D9E2EA)",
  accent: "var(--color-buoy, #E85D26)"
} as const;

function toggleButtonStyle(active: boolean): React.CSSProperties {
  return {
    appearance: "none",
    font: "inherit",
    fontSize: 12,
    fontWeight: 600,
    padding: "4px 12px",
    cursor: "pointer",
    color: active ? C.paper : C.ink,
    background: active ? C.accent : "transparent",
    border: `1px solid ${active ? C.accent : C.hairline}`
  };
}

/**
 * Figure wrapper: a Chart | Table toggle over a single series.
 *
 * Accessibility contract (documented in the README): both views live in the
 * DOM. The chart's SVG always carries the `ariaSummary` text, so even in chart
 * view a screen-reader user gets the gist; the full tabular data is one keypress
 * away via the toggle. The inactive view is removed from the tree with the
 * `hidden` attribute (not `display:none` styling alone), so its controls leave
 * the tab order. The toggle buttons are real `<button>`s carrying `aria-pressed`.
 */
export function ChartWithTable({
  kind,
  series,
  ariaSummary,
  height,
  width,
  initialView = "chart",
  onPointActivate
}: ChartWithTableProps) {
  const [view, setView] = useState<"chart" | "table">(initialView);
  const groupId = useId();
  const chartVisible = view === "chart";

  return (
    <figure className="cg-figure" style={{ margin: 0, display: "grid", gap: 12 }}>
      <div
        className="cg-toggle"
        role="group"
        aria-label={`${series.label} — choose chart or table view`}
        style={{ display: "inline-flex", width: "fit-content" }}
      >
        <button
          type="button"
          aria-pressed={chartVisible}
          data-testid="cg-toggle-chart"
          onClick={() => setView("chart")}
          style={{ ...toggleButtonStyle(chartVisible), borderRadius: "4px 0 0 4px" }}
        >
          Chart
        </button>
        <button
          type="button"
          aria-pressed={!chartVisible}
          data-testid="cg-toggle-table"
          onClick={() => setView("table")}
          style={{ ...toggleButtonStyle(!chartVisible), borderRadius: "0 4px 4px 0", borderLeft: "none" }}
        >
          Table
        </button>
      </div>

      <div id={`${groupId}-chart`} hidden={!chartVisible} data-testid="cg-chart-region">
        <ChartPlot
          kind={kind}
          series={series}
          ariaSummary={ariaSummary}
          height={height}
          width={width}
          onPointActivate={onPointActivate}
        />
      </div>

      <div id={`${groupId}-table`} hidden={chartVisible} data-testid="cg-table-region">
        <SeriesTable series={series} />
      </div>
    </figure>
  );
}
