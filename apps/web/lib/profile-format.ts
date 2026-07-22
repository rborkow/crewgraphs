import type { OrgProfilePayload, SourceRef } from "@crewgraphs/contracts";
import type { ValueFormat } from "@/lib/format";

type CoverageStatus = OrgProfilePayload["coverage"][number]["status"];

const FILING_STATUS_LABELS: Record<CoverageStatus, string> = {
  "990": "Form 990",
  "990ez": "Form 990-EZ",
  "990n": "Form 990-N",
  amended: "Amended 990",
  missing: "No filing",
  not_yet_expected: "Not yet expected"
};

/** Human label for a per-year filing-coverage status. */
export function filingStatusLabel(status: CoverageStatus): string {
  return FILING_STATUS_LABELS[status] ?? status;
}

/** True when a coverage status represents an actual filing on record. */
export function isFiledStatus(status: CoverageStatus): boolean {
  return status === "990" || status === "990ez" || status === "990n" || status === "amended";
}

const RELATIONSHIP_LABELS: Record<string, string> = {
  program_of: "Program of",
  fiscally_sponsored_by: "Fiscally sponsored by",
  successor_of: "Successor of",
  supports: "Supports",
  boosters_for: "Boosters for",
  shares_boathouse_with: "Shares a boathouse with"
};

/** Human label for an organization_relationship type. */
export function relationshipTypeLabel(type: string): string {
  if (RELATIONSHIP_LABELS[type]) return RELATIONSHIP_LABELS[type];
  const words = type.replace(/_/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Title-case a program-mix tag ("open/elite" → "Open/elite"). */
export function programLabel(tag: string): string {
  return tag.charAt(0).toUpperCase() + tag.slice(1);
}

/**
 * Format hint for a snapshot fact. Derived ratio metrics are stored as USD-unit
 * fractions (e.g. operating_margin 0.05); render those as a percent so they read
 * "5.0%", not "$0". Everything else falls back to the unit default.
 */
export function snapshotFactFormat(ref: SourceRef): ValueFormat | undefined {
  if (ref.metric && ref.value !== null && ref.unit === "USD" && Math.abs(ref.value) <= 1) {
    return "percent";
  }
  return undefined;
}

/**
 * A plain-language summary of which forms and years underlie a profile, built
 * from the filing-coverage rows. E.g. "Form 990 and Form 990-EZ for tax years
 * 2020–2024".
 */
export function coverageSourceSummary(coverage: OrgProfilePayload["coverage"]): string {
  const filed = coverage.filter((c) => isFiledStatus(c.status));
  if (filed.length === 0) return "no matched filings yet";

  const formLabels = new Set<string>();
  for (const c of filed) {
    // Amended returns are still Form 990s for the purpose of "which forms".
    formLabels.add(c.status === "amended" ? "Form 990" : filingStatusLabel(c.status));
  }
  const forms = [...formLabels];
  const formText =
    forms.length === 1
      ? forms[0]
      : `${forms.slice(0, -1).join(", ")} and ${forms[forms.length - 1]}`;

  const years = filed.map((c) => c.tax_year).sort((a, b) => a - b);
  const first = years[0];
  const last = years[years.length - 1];
  const yearText = first === last ? `tax year ${first}` : `tax years ${first}–${last}`;

  return `${formText} for ${yearText}`;
}
