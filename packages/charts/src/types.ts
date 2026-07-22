/**
 * Public data shapes for the CrewGraphs chart kit.
 *
 * `AnnualSeries` is trivially derivable from `read.org_financial_series` rows
 * (one row per key/fy) joined with `org_filing_coverage` (which supplies the
 * missing-vs-zero truth). See packages/contracts `sourceRefSchema` /
 * `filingCoverageEntrySchema` — a point's `tax_year`, `fy_end`, `value`,
 * `quality_state` and `is_amended` map 1:1 onto those columns, and `label`
 * onto `SourceRef.period.label`.
 *
 * The kit is deliberately decoupled from `@crewgraphs/contracts`: it renders
 * marks and exposes activation; the consumer keeps the full `SourceRef` map and
 * looks it up by `(series.key, point.tax_year)` when `onPointActivate` fires.
 */

/** Mirror of the db / contracts `quality_state` enum. */
export type QualityState =
  | "verified"
  | "derived"
  | "partial"
  | "unavailable"
  | "under_review";

export type SeriesUnit = "USD" | "count";

export interface AnnualPoint {
  /** IRS TaxYr — the comparison axis and the slot identity. */
  tax_year: number;
  /** Fiscal-year-end ISO date (differs from tax_year+1 for non-Dec FYE). */
  fy_end: string;
  /**
   * The value for this fiscal year.
   * - a number (incl. `0`, which is a REAL value) → a drawn mark;
   * - `null` → a MISSING filing → a visible gap, never interpolated.
   */
  value: number | null;
  quality_state: QualityState;
  /** True when the value comes from an amended return. */
  is_amended: boolean;
  /** Human period label, e.g. "FY2023" or "FY2023 (Jul 2022–Jun 2023)". */
  label: string;
}

export interface AnnualSeries {
  /** Namespaced read-model key, e.g. "concept:total_revenue". */
  key: string;
  /** Human series label, e.g. "Total revenue". */
  label: string;
  unit: SeriesUnit;
  points: AnnualPoint[];
}

export type ChartKind = "line" | "bar";

/**
 * Fired when a data point is activated (click / Enter / Space). The consumer
 * wires this to the SourceDrawer — the kit owns no drawer logic. `series` is
 * passed so one handler can serve several charts. Missing points are inert.
 */
export type PointActivateHandler = (
  point: AnnualPoint,
  series: AnnualSeries
) => void;
