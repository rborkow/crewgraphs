import {
  qualityStateSchema,
  sourceRefSchema,
  type DirectoryEntry,
  type SourceRef
} from "@crewgraphs/contracts";
import type { ValueFormat } from "@/lib/format";
import { snapshotFactFormat } from "@/lib/profile-format";

export interface ComparisonRowDefinition {
  key: string;
  label: string;
  kind: "concept" | "derived";
}

export const COMPARISON_ROWS: readonly ComparisonRowDefinition[] = [
  { key: "total_revenue", label: "Total revenue", kind: "concept" },
  { key: "total_expenses", label: "Total expenses", kind: "concept" },
  { key: "revenue_less_expenses", label: "Revenue less expenses", kind: "concept" },
  { key: "contributions_grants", label: "Contributions & grants", kind: "concept" },
  { key: "program_service_revenue", label: "Program service revenue", kind: "concept" },
  { key: "membership_dues", label: "Membership dues", kind: "concept" },
  { key: "salaries_benefits_total", label: "Salaries & benefits", kind: "concept" },
  { key: "net_assets_eoy", label: "Net assets, end of year", kind: "concept" },
  { key: "operating_margin", label: "Operating margin", kind: "derived" },
  { key: "contribution_dependency", label: "Contribution dependency", kind: "derived" },
  { key: "program_service_share", label: "Program service share", kind: "derived" },
  { key: "compensation_intensity", label: "Compensation intensity", kind: "derived" },
  { key: "membership_dues_share", label: "Membership dues share", kind: "derived" }
];

export const COMPARISON_SERIES_KEYS = COMPARISON_ROWS.map((row) => row.key);

export interface CompareSeriesRow {
  organization_id: string;
  series_key: string;
  series_version: number;
  tax_year: number;
  fiscal_year_end: Date | string;
  value: number | string | null;
  quality_state: string;
  is_amended: boolean;
  source_ref: unknown;
}

export interface ParsedOrgSlugs {
  slugs: string[];
}

/** Parse and de-duplicate the URL's comma-separated organization slugs. */
export function parseOrgSlugs(value: string | null | undefined): ParsedOrgSlugs {
  const unique = [
    ...new Set(
      (value ?? "")
        .split(",")
        .map((slug) => slug.trim())
        .filter(Boolean)
    )
  ];
  return { slugs: unique };
}

export interface ResolvedComparisonSelection {
  organizations: DirectoryEntry[];
  unknownSlugs: string[];
  overflowSlugs: string[];
}

/** Resolve URL slugs against the published directory while preserving URL order. */
export function resolveComparisonSelection(
  entries: DirectoryEntry[],
  requestedSlugs: string[]
): ResolvedComparisonSelection {
  const bySlug = new Map(entries.map((entry) => [entry.slug, entry]));
  const organizations: DirectoryEntry[] = [];
  const unknownSlugs: string[] = [];
  const overflowSlugs: string[] = [];
  for (const slug of requestedSlugs) {
    const organization = bySlug.get(slug);
    if (!organization) unknownSlugs.push(slug);
    else if (organizations.length < 4) organizations.push(organization);
    else overflowSlugs.push(slug);
  }
  return { organizations, unknownSlugs, overflowSlugs };
}

/** A TaxYr is a four-digit integer; invalid URL input falls back to defaulting. */
export function parseTaxYear(value: string | null | undefined): number | null {
  if (!value || !/^\d{4}$/.test(value)) return null;
  const year = Number(value);
  return Number.isInteger(year) ? year : null;
}

export interface ComparisonYearState {
  candidateCommonYears: number[];
  selectedYear: number | null;
  usedNoCommonYearFallback: boolean;
}

export function deriveComparisonYear(
  organizations: DirectoryEntry[],
  explicitYear: number | null
): ComparisonYearState {
  if (organizations.length === 0) {
    return { candidateCommonYears: [], selectedYear: explicitYear, usedNoCommonYearFallback: false };
  }

  const common = organizations[0].filing_years.filter((year) =>
    organizations.slice(1).every((organization) => organization.filing_years.includes(year))
  );
  const candidateCommonYears = [...new Set(common)].sort((a, b) => b - a);
  if (explicitYear !== null) {
    return { candidateCommonYears, selectedYear: explicitYear, usedNoCommonYearFallback: false };
  }
  if (candidateCommonYears.length > 0) {
    return {
      candidateCommonYears,
      selectedYear: candidateCommonYears[0],
      usedNoCommonYearFallback: false
    };
  }

  // With no common TaxYr, comparison stays useful by choosing the newest year
  // filed by any selected org; every other org gets an explicit unavailable cell.
  const allYears = organizations.flatMap((organization) => organization.filing_years);
  return {
    candidateCommonYears,
    selectedYear: allYears.length > 0 ? Math.max(...allYears) : null,
    usedNoCommonYearFallback: allYears.length > 0
  };
}

export interface ComparisonCell {
  ref: SourceRef;
  fiscalYearEnd: string;
  qualityState: SourceRef["quality_state"];
  isAmended: boolean;
  suppressed: boolean;
}

export interface ComparisonViewRow extends ComparisonRowDefinition {
  cells: Partial<Record<string, ComparisonCell>>;
}

function numberValue(value: CompareSeriesRow["value"]): number | null {
  if (value === null) return null;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function isoDate(value: Date | string): string {
  return value instanceof Date ? value.toISOString().slice(0, 10) : String(value).slice(0, 10);
}

function latestRows(rows: CompareSeriesRow[]): Map<string, CompareSeriesRow> {
  const latest = new Map<string, CompareSeriesRow>();
  for (const row of rows) {
    const key = `${row.organization_id}::${row.series_key}`;
    const current = latest.get(key);
    if (!current || row.series_version >= current.series_version) latest.set(key, row);
  }
  return latest;
}

/** Contract-validate and arrange the selected year's long rows into table cells. */
export function buildComparisonRows(rows: CompareSeriesRow[]): ComparisonViewRow[] {
  const latest = latestRows(rows);
  return COMPARISON_ROWS.map((definition) => {
    const cells: Partial<Record<string, ComparisonCell>> = {};
    for (const row of latest.values()) {
      if (row.series_key !== definition.key) continue;
      const qualityState = qualityStateSchema.parse(row.quality_state);
      const sourceRef = sourceRefSchema.parse(row.source_ref);
      const suppressed = qualityState === "under_review";
      cells[row.organization_id] = {
        ref: {
          ...sourceRef,
          value: suppressed ? null : numberValue(row.value),
          quality_state: qualityState,
          source: { ...sourceRef.source, is_amended: row.is_amended }
        },
        fiscalYearEnd: isoDate(row.fiscal_year_end),
        qualityState,
        isAmended: row.is_amended,
        suppressed
      };
    }
    return { ...definition, cells };
  });
}

/** Derived comparison metrics use the profile's fraction-valued percent idiom. */
export function comparisonCellFormat(
  definition: ComparisonRowDefinition,
  ref: SourceRef
): ValueFormat | undefined {
  return definition.kind === "derived" ? (snapshotFactFormat(ref) ?? "percent") : undefined;
}

export function fyeMonthLabel(month: number | null): string {
  if (month === null) return "FYE unavailable";
  const label = new Intl.DateTimeFormat("en-US", { month: "short", timeZone: "UTC" }).format(
    new Date(Date.UTC(2024, month - 1, 1))
  );
  return `FYE ${label}`;
}

export function organizationsHaveDifferentFyes(organizations: DirectoryEntry[]): boolean {
  const knownMonths = new Set(
    organizations.flatMap((organization) =>
      organization.fye_month === null ? [] : [organization.fye_month]
    )
  );
  return knownMonths.size > 1;
}

export interface CompareCsvRow {
  org: string;
  series_key: string;
  label: string;
  tax_year: number;
  fiscal_year_end: string;
  value: number | null;
  quality_state: SourceRef["quality_state"];
  is_amended: boolean;
  source_path: string;
}

/** Build export rows in URL organization order and table row order. */
export function buildCompareCsvRows(
  rows: CompareSeriesRow[],
  organizations: DirectoryEntry[]
): CompareCsvRow[] {
  const latest = latestRows(rows);
  const output: CompareCsvRow[] = [];
  for (const organization of organizations) {
    for (const definition of COMPARISON_ROWS) {
      const row = latest.get(`${organization.org_id}::${definition.key}`);
      if (!row || row.quality_state === "under_review") continue;
      const ref = sourceRefSchema.parse(row.source_ref);
      output.push({
        org: organization.display_name,
        series_key: definition.key,
        label: definition.label,
        tax_year: row.tax_year,
        fiscal_year_end: isoDate(row.fiscal_year_end),
        value: numberValue(row.value),
        quality_state: qualityStateSchema.parse(row.quality_state),
        is_amended: row.is_amended,
        source_path: ref.source.source_path
      });
    }
  }
  return output;
}

const CSV_COLUMNS: ReadonlyArray<keyof CompareCsvRow> = [
  "org",
  "series_key",
  "label",
  "tax_year",
  "fiscal_year_end",
  "value",
  "quality_state",
  "is_amended",
  "source_path"
];

function csvField(value: CompareCsvRow[keyof CompareCsvRow]): string {
  const text = value === null ? "" : String(value);
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function serializeCompareCsv(rows: CompareCsvRow[]): string {
  const lines = [CSV_COLUMNS.join(",")];
  for (const row of rows) lines.push(CSV_COLUMNS.map((column) => csvField(row[column])).join(","));
  return `${lines.join("\r\n")}\r\n`;
}
