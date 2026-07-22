/**
 * @crewgraphs/charts — hand-rolled SVG chart kit for CrewGraphs.
 *
 * Tiny annual financial series for nonprofit rowing clubs (≤ ~8 points, one
 * series per chart). Static SVG that server-renders inside RSC and hydrates only
 * to wire per-point buttons and the chart/table toggle. See README for the
 * interaction + accessibility model and the missing-vs-zero-vs-amended rules.
 */

export { AnnualSeriesChart, type AnnualSeriesChartProps } from "./AnnualSeriesChart";
export { SeriesTable, type SeriesTableProps } from "./SeriesTable";
export { ChartWithTable, type ChartWithTableProps } from "./ChartWithTable";

export { formatUSD, formatCount, formatValue, qualityLabel, type FormatOptions } from "./format";

export { buildGeometry, type Geometry, type Mark, type AxisTick } from "./geometry";

export type {
  AnnualSeries,
  AnnualPoint,
  ChartKind,
  QualityState,
  SeriesUnit,
  PointActivateHandler
} from "./types";
