import type { SourceRef } from "@crewgraphs/contracts";

export type ValueFormat = "currency" | "count" | "percent";

const currencyFmt = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0
});

const countFmt = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

const percentFmt = new Intl.NumberFormat("en-US", {
  style: "percent",
  maximumFractionDigits: 1
});

/** Choose a sensible default format from the SourceRef unit when none is given. */
export function defaultFormatForUnit(unit: SourceRef["unit"]): ValueFormat {
  return unit === "count" ? "count" : "currency";
}

/**
 * Format a numeric metric value for display. `percent` treats the value as a
 * ratio (0.08 → "8%"), matching how derived ratio metrics are stored.
 */
export function formatValue(value: number, format: ValueFormat): string {
  switch (format) {
    case "currency":
      return currencyFmt.format(value);
    case "percent":
      return percentFmt.format(value);
    case "count":
    default:
      return countFmt.format(value);
  }
}

/** Exact, unrounded value + unit for the source drawer header. */
export function formatExact(value: number, unit: SourceRef["unit"]): string {
  const exact = new Intl.NumberFormat("en-US").format(value);
  return unit === "USD" ? `$${exact}` : `${exact}`;
}

const DATETIME_FMT = new Intl.DateTimeFormat("en-US", {
  year: "numeric",
  month: "short",
  day: "numeric"
});

/** Human date for a `retrieved_at` / `fy_end` ISO string. */
export function formatDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : DATETIME_FMT.format(d);
}

const ORG_TYPE_LABELS: Record<string, string> = {
  community_club: "Community club",
  private_membership_club: "Private membership club",
  scholastic_program: "Scholastic program",
  collegiate_varsity: "Collegiate varsity",
  collegiate_club: "Collegiate club",
  university_support_foundation: "University support foundation",
  booster_club: "Booster club",
  adaptive_program: "Adaptive program",
  association: "Association",
  governing_body: "Governing body",
  other: "Other"
};

export function orgTypeLabel(orgType: string): string {
  return ORG_TYPE_LABELS[orgType] ?? "Organization";
}
