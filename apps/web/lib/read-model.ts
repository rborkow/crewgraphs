import {
  directoryEntrySchema,
  orgProfilePayloadSchema,
  sourceRefSchema,
  type DirectoryBlob,
  type DirectoryEntry,
  type OrgProfilePayload,
  type SourceRef
} from "@crewgraphs/contracts";
import type { AnnualSeries, ChartKind, QualityState, SeriesUnit } from "@crewgraphs/charts";
import { formatUSD, formatCount } from "@crewgraphs/charts";
import { formatDate } from "@/lib/format";
import { isFiledStatus } from "@/lib/profile-format";

/**
 * Pure read-model mappers: DB rows in, contract-validated view shapes out.
 *
 * This module holds NO database I/O — `db.ts` owns that. Keeping the transforms
 * here means they can be unit-tested against fixture-shaped rows entirely
 * offline (see read-model.test.ts), and the contract schemas act as the gate at
 * the boundary: a payload or entry that fails validation throws rather than
 * rendering something unprovenanced.
 */

// ---------------------------------------------------------------------------
// Raw DB row shapes (as node-pg returns them)
// ---------------------------------------------------------------------------

/** A `read.org_financial_series` row. `numeric` comes back as a string. */
export interface FinancialSeriesRow {
  series_key: string;
  tax_year: number;
  value: number | string | null;
  quality_state: string;
  is_amended: boolean;
  source_ref: unknown;
}

/** The `read.org_directory` columns joined with the profile payload. */
export interface DirectoryJoinRow {
  organization_id: string;
  slug: string;
  display_name: string;
  aliases: unknown;
  coverage_state: string;
  fye_month: number | null;
  payload: unknown;
}

/** A `read.org_slug_history` row. */
export interface SlugHistoryRow {
  slug: string;
  org_id: string;
  is_current: boolean;
}

/** `read.published_snapshot` singleton fields the web tier consumes. */
export interface PublishedSnapshotRow {
  snapshot_id: string;
  updated_at: Date | string;
}

function toNumber(value: number | string | null): number | null {
  if (value === null) return null;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isNaN(n) ? null : n;
}

function toIso(value: Date | string): string {
  return value instanceof Date ? value.toISOString() : value;
}

// ---------------------------------------------------------------------------
// Profile payload
// ---------------------------------------------------------------------------

/** Parse a `read.org_profile.payload` through the contract; throws when invalid. */
export function mapProfilePayload(payload: unknown): OrgProfilePayload {
  return orgProfilePayloadSchema.parse(payload);
}

// ---------------------------------------------------------------------------
// Financial series (trends) + chart-point provenance
// ---------------------------------------------------------------------------

/** Human labels for the charted concepts. */
const SERIES_LABELS: Record<string, string> = {
  total_revenue: "Total revenue",
  total_expenses: "Total expenses"
};

/**
 * The concept series rendered as financial-trend charts. The read model carries
 * many namespaced keys (net assets, derived ratios, …) but revenue and expenses
 * are the annual trajectory; other facts live in the snapshot, not as charts.
 */
const TREND_SERIES_KEYS = ["total_revenue", "total_expenses"] as const;

/** The provenance-map key the chart consumer looks up on point activation. */
export function provenanceKey(seriesKey: string, taxYear: number): string {
  return `${seriesKey}::${taxYear}`;
}

export interface TrendChart {
  series: AnnualSeries;
  ariaSummary: string;
  kind: ChartKind;
}

export interface Trends {
  charts: TrendChart[];
  /** SourceRef by `${series_key}::${tax_year}` — opens the chart-point drawer. */
  provenance: Record<string, SourceRef>;
}

const NUMBER_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight"];

function numberWord(n: number): string {
  return NUMBER_WORDS[n] ?? String(n);
}

/**
 * One honest sentence describing a series for the SVG `aria-label`, calling out
 * missing and amended fiscal years explicitly (they are product facts, not
 * noise). E.g. "Total revenue, five fiscal years FY2020–FY2024, ranging
 * $180,000–$310,000; FY2021 missing."
 */
function buildAriaSummary(series: AnnualSeries): string {
  const points = series.points;
  const fmt = (v: number) => (series.unit === "USD" ? formatUSD(v) : formatCount(v));
  const first = points[0].tax_year;
  const last = points[points.length - 1].tax_year;
  const span = points.length === 1 ? `FY${first}` : `FY${first}–FY${last}`;

  const values = points.filter((p) => p.value !== null).map((p) => p.value as number);
  const missing = points.filter((p) => p.value === null).map((p) => `FY${p.tax_year}`);
  const amended = points.filter((p) => p.is_amended).map((p) => `FY${p.tax_year}`);

  let body: string;
  if (values.length === 0) body = "no reported values";
  else if (values.length === 1) body = fmt(values[0]);
  else body = `ranging ${fmt(Math.min(...values))}–${fmt(Math.max(...values))}`;

  const yearWord = points.length === 1 ? "fiscal year" : "fiscal years";
  let summary = `${series.label}, ${numberWord(points.length)} ${yearWord} ${span}, ${body}`;
  if (missing.length > 0) summary += `; ${missing.join(", ")} missing`;
  if (amended.length > 0) summary += `; ${amended.join(", ")} amended`;
  return `${summary}.`;
}

interface NormalizedSeriesRow {
  tax_year: number;
  value: number | null;
  quality_state: QualityState;
  is_amended: boolean;
  fy_end: string;
  label: string;
  unit: SeriesUnit;
}

function normalizeSeriesRow(row: FinancialSeriesRow): NormalizedSeriesRow {
  const ref = sourceRefSchema.parse(row.source_ref);
  return {
    tax_year: row.tax_year,
    value: toNumber(row.value),
    quality_state: row.quality_state as QualityState,
    is_amended: row.is_amended,
    fy_end: ref.period.fy_end,
    label: ref.period.label,
    unit: ref.unit
  };
}

/**
 * Group `read.org_financial_series` rows into the charted `AnnualSeries` shapes
 * plus the chart-point provenance map, mirroring how the fixtures grouped them:
 * one Chart|Table figure per charted concept (revenue, expenses), a single filed
 * year rendered as a bar, a real multi-year trend as a line.
 *
 * The published series omits missing fiscal years entirely (unlike the older
 * fixtures, which encoded explicit null rows). To keep the missing-vs-zero
 * product rule legible, a null point is injected for any coverage year that
 * falls within a concept's span but has no value — a visible gap, never
 * interpolated. Rows that already carry a null value (fixture shape) are used as
 * they are, so the same function serves live rows and fixture rows.
 */
export function groupTrends(
  rows: FinancialSeriesRow[],
  coverage: OrgProfilePayload["coverage"]
): Trends {
  const provenance: Record<string, SourceRef> = {};
  for (const row of rows) {
    provenance[provenanceKey(row.series_key, row.tax_year)] = sourceRefSchema.parse(row.source_ref);
  }

  const coverageByYear = new Map(coverage.map((c) => [c.tax_year, c]));

  const charts: TrendChart[] = [];
  for (const key of TREND_SERIES_KEYS) {
    const keyRows = rows
      .filter((row) => row.series_key === key)
      .map(normalizeSeriesRow);
    if (keyRows.length === 0) continue;

    const rowByYear = new Map(keyRows.map((r) => [r.tax_year, r]));
    const valued = keyRows.filter((r) => r.value !== null);
    if (valued.length === 0) continue;

    const minYear = Math.min(...valued.map((r) => r.tax_year));
    const maxYear = Math.max(...valued.map((r) => r.tax_year));

    // Axis years: every year the concept has a row for, plus any coverage year
    // between the first and last valued year (so an interior missing filing
    // shows as a gap rather than a silently collapsed axis).
    const years = new Set<number>(keyRows.map((r) => r.tax_year));
    for (const c of coverage) {
      if (c.tax_year >= minYear && c.tax_year <= maxYear) years.add(c.tax_year);
    }

    const unit = keyRows[0].unit;
    const points = [...years]
      .sort((a, b) => a - b)
      .map((taxYear) => {
        const row = rowByYear.get(taxYear);
        if (row) {
          return {
            tax_year: taxYear,
            fy_end: row.fy_end,
            value: row.value,
            quality_state: row.quality_state,
            is_amended: row.is_amended,
            label: row.label
          };
        }
        // Coverage year with no series value → an injected missing point.
        const cov = coverageByYear.get(taxYear);
        return {
          tax_year: taxYear,
          fy_end: cov?.fy_end ?? "",
          value: null,
          quality_state: "unavailable" as QualityState,
          is_amended: false,
          label: `FY${taxYear}`
        };
      });

    const series: AnnualSeries = {
      key,
      label: SERIES_LABELS[key] ?? key,
      unit,
      points
    };
    charts.push({
      series,
      ariaSummary: buildAriaSummary(series),
      // A single filed year is a bar (a lone dot reads as an error); a real
      // multi-year trend is a line.
      kind: series.points.length >= 2 ? "line" : "bar"
    });
  }

  return { charts, provenance };
}

// ---------------------------------------------------------------------------
// Slug resolution
// ---------------------------------------------------------------------------

export type SlugResolution =
  | { kind: "current"; slug: string }
  | { kind: "redirect"; slug: string }
  | { kind: "not_found" };

/**
 * Resolve an incoming slug to a current page, a permanent-redirect target, or a
 * 404, from the published directory + slug-history rows. A non-current slug in
 * `read.org_slug_history` resolves to whatever slug that org is currently
 * published under (old slugs are never reused).
 */
export function resolveFromRows(
  slug: string,
  directoryRows: Array<{ organization_id: string; slug: string }>,
  historyRows: SlugHistoryRow[]
): SlugResolution {
  const currentSlugs = new Set(directoryRows.map((r) => r.slug));
  if (currentSlugs.has(slug)) return { kind: "current", slug };

  const historical = historyRows.find((h) => h.slug === slug && !h.is_current);
  if (historical) {
    const current = directoryRows.find((r) => r.organization_id === historical.org_id);
    if (current) return { kind: "redirect", slug: current.slug };
  }
  return { kind: "not_found" };
}

// ---------------------------------------------------------------------------
// Directory assembly
// ---------------------------------------------------------------------------

/**
 * Assemble one full `DirectoryEntry` from the thin `org_directory` row joined
 * with the org's profile payload: the payload header supplies org_type /
 * program_mix / city / state, and coverage + snapshot facts derive
 * filing_years / latest_tax_year / latest_total_revenue. The result is validated
 * through `directoryEntrySchema` so a bad assembly fails loudly.
 */
export function assembleDirectoryEntry(row: DirectoryJoinRow): DirectoryEntry {
  const payload = mapProfilePayload(row.payload);

  const filingYears = payload.coverage
    .filter((c) => isFiledStatus(c.status))
    .map((c) => c.tax_year)
    .sort((a, b) => a - b);
  const latestTaxYear = filingYears.length > 0 ? filingYears[filingYears.length - 1] : null;
  const revenueFact = payload.snapshot.find((f) => f.key === "total_revenue");

  return directoryEntrySchema.parse({
    org_id: row.organization_id,
    slug: row.slug,
    display_name: row.display_name,
    aliases: Array.isArray(row.aliases) ? row.aliases : [],
    city: payload.header.city,
    state: payload.header.state,
    org_type: payload.header.org_type,
    program_mix: payload.header.program_mix,
    // Peer cohorts are not part of the published read model yet; an empty list
    // is a valid entry and simply hides the cohort facet.
    peer_cohorts: [],
    coverage_state: row.coverage_state,
    filing_years: filingYears,
    latest_tax_year: latestTaxYear,
    latest_total_revenue: revenueFact ? revenueFact.ref.value : null,
    fye_month: row.fye_month
  });
}

/** "Data through the <formatted> publish", from `published_snapshot.updated_at`. */
export function buildDataThroughLabel(updatedAt: Date | string): string {
  return `Data through the ${formatDate(toIso(updatedAt))} publish`;
}

/** Assemble the full directory blob (validated entries + publish metadata). */
export function assembleDirectory(
  snapshot: PublishedSnapshotRow,
  rows: DirectoryJoinRow[]
): DirectoryBlob {
  const publishedAt = toIso(snapshot.updated_at);
  return {
    snapshot_id: snapshot.snapshot_id,
    published_at: publishedAt,
    data_through_label: buildDataThroughLabel(snapshot.updated_at),
    entries: rows
      .map(assembleDirectoryEntry)
      .sort((a, b) => a.display_name.localeCompare(b.display_name))
  };
}
