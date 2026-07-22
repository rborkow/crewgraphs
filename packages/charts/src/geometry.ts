import { scaleBand, scaleLinear } from "d3-scale";
import { line } from "d3-shape";
import { formatValue, qualityLabel } from "./format";
import type { AnnualSeries, ChartKind } from "./types";

/**
 * Pure chart geometry. No React, no DOM measurement — everything is computed in
 * a fixed viewBox coordinate space so the server and client produce byte-
 * identical SVG, and the HTML overlay can be positioned by percentage (which
 * tracks the SVG as it scales to 100% width).
 *
 * Design rules baked in here (see the MVP spec "Web surface" + design language):
 * - a MISSING year (`value === null`) is a GAP: the line breaks (d3 `defined`),
 *   the bar leaves a hatched empty slot; never interpolated;
 * - ZERO is a real value: a mark at/near the baseline, distinct from a gap;
 * - `partial` / `under_review` render hollow/dashed (never color-only);
 * - amended points get a triangle overlay + "(amended)" in the accessible name;
 * - baseline + at most 3 hairlines; no gridline soup.
 */

export interface GeometryOptions {
  kind: ChartKind;
  /** viewBox width. Default 640. */
  width?: number;
  /** viewBox height. Default 220. */
  height?: number;
}

export interface AxisTick {
  value: number;
  /** y in viewBox coords. */
  y: number;
  /** compact label, e.g. "$1.3M". */
  label: string;
}

export interface XTick {
  /** center x in viewBox coords. */
  x: number;
  label: string;
}

/** One period's fully-resolved drawing + accessibility instructions. */
export interface Mark {
  index: number;
  tax_year: number;
  /** Period label (from the point). */
  periodLabel: string;
  quality: string;
  isMissing: boolean;
  isZero: boolean;
  /** partial | under_review → hollow/dashed treatment. */
  isHollow: boolean;
  isAmended: boolean;
  /** slot center x in viewBox coords. */
  cx: number;
  /**
   * The mark's data-end y in viewBox coords (top of a bar, the dot centre).
   * For a missing slot this is the plot's vertical centre (button anchor).
   */
  cy: number;
  /** overlay button position as a percentage of the viewBox. */
  xPct: number;
  yPct: number;
  /** Present, non-missing bar path (top/bottom rounded, baseline-anchored). */
  barPath: string | null;
  /** Amended triangle path (apex-up marker above the data end). */
  amendedMarker: string | null;
  /** Missing-slot hatched rect (bar) in viewBox coords. */
  missingRect: { x: number; y: number; width: number; height: number } | null;
  /** Full accessible name for the overlay button. */
  accessibleName: string;
}

export interface Geometry {
  width: number;
  height: number;
  plot: { top: number; right: number; bottom: number; left: number };
  baselineY: number;
  bandWidth: number;
  marks: Mark[];
  /** `null` for bar charts, or when fewer than two points are defined. */
  linePath: string | null;
  hairlines: AxisTick[];
  yTicks: AxisTick[];
  xTicks: XTick[];
}

const MARGIN = { top: 16, right: 16, bottom: 28, left: 54 };

/** Rounded-top rect anchored to a baseline at `y + h` (data-end at `y`). */
function topRoundedRect(x: number, y: number, w: number, h: number, r: number): string {
  const rr = Math.max(0, Math.min(r, w / 2, h));
  return (
    `M${x},${y + h} L${x},${y + rr} Q${x},${y} ${x + rr},${y} ` +
    `L${x + w - rr},${y} Q${x + w},${y} ${x + w},${y + rr} L${x + w},${y + h} Z`
  );
}

/** Rounded-bottom rect anchored to a baseline at `y` (data-end at `y + h`). */
function bottomRoundedRect(x: number, y: number, w: number, h: number, r: number): string {
  const rr = Math.max(0, Math.min(r, w / 2, h));
  return (
    `M${x},${y} L${x},${y + h - rr} Q${x},${y + h} ${x + rr},${y + h} ` +
    `L${x + w - rr},${y + h} Q${x + w},${y + h} ${x + w},${y + h - rr} L${x + w},${y} Z`
  );
}

export function buildGeometry(series: AnnualSeries, opts: GeometryOptions): Geometry {
  const width = opts.width ?? 640;
  const height = opts.height ?? 220;
  const plotBottom = height - MARGIN.bottom;
  const plotTop = MARGIN.top;

  const points = series.points;
  const years = points.map((p) => p.tax_year);

  const xb = scaleBand<number>()
    .domain(years)
    .range([MARGIN.left, width - MARGIN.right])
    .paddingInner(0.4)
    .paddingOuter(0.28);
  const bandWidth = xb.bandwidth();

  const defined = points.filter((p) => p.value !== null);
  const values = defined.map((p) => p.value as number);
  const rawMax = values.length ? Math.max(...values) : 1;
  const rawMin = values.length ? Math.min(...values) : 0;
  // 0 is always in the domain so the baseline is a true zero line.
  const domainMax = Math.max(0, rawMax) || 1;
  const domainMin = Math.min(0, rawMin);

  const y = scaleLinear()
    .domain([domainMin, domainMax])
    .range([plotBottom, plotTop])
    .nice(4);

  const baselineY = y(0);

  const centerX = (year: number) => (xb(year) ?? 0) + bandWidth / 2;

  // Baseline + at most 3 hairlines. Hairlines are the non-zero ticks.
  const ticks = y.ticks(4);
  const hairlines: AxisTick[] = ticks
    .filter((t) => t !== 0)
    .slice(0, 3)
    .map((t) => ({ value: t, y: y(t), label: formatValue(t, series.unit, { compact: true }) }));
  const yTicks: AxisTick[] = ticks.map((t) => ({
    value: t,
    y: y(t),
    label: formatValue(t, series.unit, { compact: true })
  }));

  const xTicks: XTick[] = points.map((p) => ({ x: centerX(p.tax_year), label: `FY${p.tax_year}` }));

  const marks: Mark[] = points.map((p, index) => {
    const cx = centerX(p.tax_year);
    const isMissing = p.value === null;
    const value = p.value ?? 0;
    const isZero = !isMissing && value === 0;
    const isHollow = p.quality_state === "partial" || p.quality_state === "under_review";
    const isAmended = p.is_amended;

    // The mark's data-end y (top of bar / dot centre); missing → plot centre.
    let cy: number;
    if (isMissing) {
      cy = (plotTop + plotBottom) / 2;
    } else if (isZero) {
      cy = baselineY;
    } else {
      cy = y(value);
    }

    let barPath: string | null = null;
    let missingRect: Mark["missingRect"] = null;
    if (opts.kind === "bar") {
      const bx = xb(p.tax_year) ?? 0;
      if (isMissing) {
        missingRect = { x: bx, y: plotTop, width: bandWidth, height: plotBottom - plotTop };
      } else if (isZero) {
        // A 2px nub at the baseline — a real, visible zero, unlike a gap.
        missingRect = null;
        barPath = topRoundedRect(bx, baselineY - 2, bandWidth, 2, 1);
      } else if (value > 0) {
        const top = y(value);
        barPath = topRoundedRect(bx, top, bandWidth, baselineY - top, 4);
      } else {
        const bottom = y(value);
        barPath = bottomRoundedRect(bx, baselineY, bandWidth, bottom - baselineY, 4);
      }
    }

    // Amended triangle marker, apex-up, sitting just above the data end.
    let amendedMarker: string | null = null;
    if (isAmended && !isMissing) {
      const ty = cy - 9;
      amendedMarker = `M${cx},${ty} L${cx + 5},${ty + 8} L${cx - 5},${ty + 8} Z`;
    }

    const valueText = isMissing ? "no filing" : formatValue(value, series.unit);
    const accessibleName = isMissing
      ? `${p.label} — no filing`
      : `${p.label} ${series.label} ${valueText}, ${qualityLabel(p.quality_state)}` +
        (isAmended ? " (amended)" : "");

    return {
      index,
      tax_year: p.tax_year,
      periodLabel: p.label,
      quality: p.quality_state,
      isMissing,
      isZero,
      isHollow,
      isAmended,
      cx,
      cy,
      xPct: (cx / width) * 100,
      yPct: (cy / height) * 100,
      barPath,
      amendedMarker,
      missingRect,
      accessibleName
    };
  });

  // Line path with true gaps: undefined at every missing year (never bridged).
  let linePath: string | null = null;
  if (opts.kind === "line") {
    const gen = line<(typeof points)[number]>()
      .defined((p) => p.value !== null)
      .x((p) => centerX(p.tax_year))
      .y((p) => y(p.value as number));
    linePath = gen(points) || null;
  }

  return {
    width,
    height,
    plot: { top: plotTop, right: MARGIN.right, bottom: plotBottom, left: MARGIN.left },
    baselineY,
    bandWidth,
    marks,
    linePath,
    hairlines,
    yTicks,
    xTicks
  };
}
