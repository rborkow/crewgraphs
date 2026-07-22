import {
  orgProfilePayloadSchema,
  type OrgProfilePayload,
  type SourceRef
} from "@crewgraphs/contracts";
import type { AnnualSeries, ChartKind, QualityState, SeriesUnit } from "@crewgraphs/charts";
import { formatUSD, formatCount } from "@crewgraphs/charts";

// Profile content: static imports of the fixture payloads, each validated
// through the shared contract at module scope so drift fails loudly. In
// production this whole module is the seam where the real read-model query
// (read.org_profile / read.org_financial_series) swaps in; nothing above it
// knows the data comes from fixtures.
import bayward from "../../../db/fixtures/payloads/bayward-community-rowing.json";
import blueHeron from "../../../db/fixtures/payloads/blue-heron-community-oars.json";
import cedarPoint from "../../../db/fixtures/payloads/cedar-point-barge-club.json";
import cobalt from "../../../db/fixtures/payloads/cobalt-reach-club.json";
import harborview from "../../../db/fixtures/payloads/harborview-scholastic-oars.json";
import juniper from "../../../db/fixtures/payloads/juniper-creek-rowing.json";
import larkspur from "../../../db/fixtures/payloads/larkspur-river-adaptive.json";
import millbrook from "../../../db/fixtures/payloads/millbrook-community-rowing.json";
import northfield from "../../../db/fixtures/payloads/northfield-masters-rowing.json";
import pineglass from "../../../db/fixtures/payloads/pineglass-collegiate-club.json";
import redstone from "../../../db/fixtures/payloads/redstone-river-collective.json";
import silverplain from "../../../db/fixtures/payloads/silverplain-river-collective.json";

import seriesJson from "../../../db/fixtures/series.json";

// ---------------------------------------------------------------------------
// Profiles
// ---------------------------------------------------------------------------

const RAW_PAYLOADS: unknown[] = [
  bayward,
  blueHeron,
  cedarPoint,
  cobalt,
  harborview,
  juniper,
  larkspur,
  millbrook,
  northfield,
  pineglass,
  redstone,
  silverplain
];

const PROFILES: Map<string, OrgProfilePayload> = new Map(
  RAW_PAYLOADS.map((raw) => {
    const payload = orgProfilePayloadSchema.parse(raw);
    return [payload.slug, payload] as const;
  })
);

/**
 * Renamed-org slug history: `read.org_slug_history` non-current rows. Old slugs
 * are never reused; a request for one must permanent-redirect (301/308) to the
 * organization's current slug. Hardcoded from the fixtures (story-10 org,
 * Redstone, was published under an earlier slug).
 */
export const SLUG_HISTORY: Record<string, string> = {
  "redstone-river-club-301s": "redstone-river-collective"
};

/** Current, canonical slugs — the pages that render directly. */
export function getCurrentSlugs(): string[] {
  return [...PROFILES.keys()].sort();
}

/** Every slug the route must respond to: current pages plus 301 sources. */
export function getRouteSlugs(): string[] {
  return [...getCurrentSlugs(), ...Object.keys(SLUG_HISTORY)].sort();
}

export type SlugResolution =
  | { kind: "current"; slug: string }
  | { kind: "redirect"; slug: string }
  | { kind: "not_found" };

/** Resolve an incoming slug to a current page, a 301 target, or a 404. */
export function resolveSlug(slug: string): SlugResolution {
  if (PROFILES.has(slug)) return { kind: "current", slug };
  const redirectTo = SLUG_HISTORY[slug];
  if (redirectTo) return { kind: "redirect", slug: redirectTo };
  return { kind: "not_found" };
}

export function getProfile(slug: string): OrgProfilePayload | null {
  return PROFILES.get(slug) ?? null;
}

// ---------------------------------------------------------------------------
// Financial series (trends) + chart-point provenance
// ---------------------------------------------------------------------------

interface SeriesJsonRow {
  series_key: string;
  tax_year: number;
  fy_end: string;
  value: number | null;
  quality_state: string;
  is_amended: boolean;
  unit: string;
  source_ref: SourceRef;
}

const SERIES_BY_SLUG = seriesJson as unknown as Record<string, SeriesJsonRow[]>;

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

function toAnnualSeries(seriesKey: string, rows: SeriesJsonRow[]): AnnualSeries {
  const points = [...rows]
    .sort((a, b) => a.tax_year - b.tax_year)
    .map((row) => ({
      tax_year: row.tax_year,
      fy_end: row.fy_end,
      value: row.value,
      quality_state: row.quality_state as QualityState,
      is_amended: row.is_amended,
      label: row.source_ref.period.label
    }));
  return {
    key: seriesKey,
    label: SERIES_LABELS[seriesKey] ?? seriesKey,
    unit: (rows[0]?.unit as SeriesUnit) ?? "USD",
    points
  };
}

/**
 * Financial-trend charts + the chart-point provenance map for an org. Returns
 * empty charts when the org has no chartable series (e.g. a 990-N-only filer);
 * the caller renders the coverage explainer instead of an empty chart.
 */
export function getTrends(slug: string): Trends {
  const rows = SERIES_BY_SLUG[slug] ?? [];
  const provenance: Record<string, SourceRef> = {};
  for (const row of rows) {
    provenance[provenanceKey(row.series_key, row.tax_year)] = row.source_ref;
  }

  const charts: TrendChart[] = [];
  for (const key of TREND_SERIES_KEYS) {
    const keyRows = rows.filter((row) => row.series_key === key);
    if (keyRows.length === 0) continue;
    const series = toAnnualSeries(key, keyRows);
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
