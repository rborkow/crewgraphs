"use client";

import { ChartPlot } from "./ChartPlot";
import type { AnnualSeries, ChartKind, PointActivateHandler } from "./types";

export interface AnnualSeriesChartProps {
  kind: ChartKind;
  series: AnnualSeries;
  /** One honest sentence describing the series; goes on the SVG `aria-label`. */
  ariaSummary: string;
  /** viewBox height (px in coordinate space). Default 220. */
  height?: number;
  /** viewBox width (px in coordinate space). Default 640. */
  width?: number;
  onPointActivate?: PointActivateHandler;
}

/**
 * A single annual financial series as a static SVG line or bar chart.
 *
 * Server-renders to static SVG (the geometry is deterministic — no DOM
 * measurement), then hydrates only to wire the per-point buttons to
 * `onPointActivate`. Standalone-usable; when paired with the table, prefer
 * `ChartWithTable`.
 */
export function AnnualSeriesChart({
  kind,
  series,
  ariaSummary,
  height,
  width,
  onPointActivate
}: AnnualSeriesChartProps) {
  return (
    <figure className="cg-chart" style={{ margin: 0 }}>
      <ChartPlot
        kind={kind}
        series={series}
        ariaSummary={ariaSummary}
        height={height}
        width={width}
        onPointActivate={onPointActivate}
      />
    </figure>
  );
}
