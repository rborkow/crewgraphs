import { z } from "zod";

/**
 * Pure mappers for the /methods read models: `read.metric_catalog` and
 * `read.source_registry_public` payloads in, validated view shapes out.
 *
 * Follows the same boundary rule as `read-model.ts`: these payloads are
 * publish-built jsonb, so they are parsed through a zod schema at the seam and
 * an invalid payload throws rather than rendering. No database I/O here —
 * `methods-data.ts` owns that.
 */

// ---------------------------------------------------------------------------
// Metric catalog — read.metric_catalog.payload
// ---------------------------------------------------------------------------

export const metricCatalogPayloadSchema = z.object({
  key: z.string(),
  version: z.number().int(),
  label: z.string(),
  description: z.string(),
  unit: z.string(),
  /** Machine-readable eligibility rule, e.g. {"min_observations": 3}. */
  eligibility_rule: z.record(z.string(), z.unknown()),
  limitation: z.string().nullable()
});

export type MetricCatalogEntry = z.infer<typeof metricCatalogPayloadSchema>;

/**
 * Validate raw catalog payloads and keep only the newest version per metric
 * key (older versions stay published for provenance, but the catalog page
 * documents the current definition). Sorted by label for stable display.
 */
export function mapMetricCatalog(payloads: unknown[]): MetricCatalogEntry[] {
  const newest = new Map<string, MetricCatalogEntry>();
  for (const payload of payloads) {
    const entry = metricCatalogPayloadSchema.parse(payload);
    const current = newest.get(entry.key);
    if (!current || entry.version > current.version) newest.set(entry.key, entry);
  }
  return [...newest.values()].sort((a, b) => a.label.localeCompare(b.label));
}

/**
 * Render an eligibility rule as plain-language conditions. Known rule keys are
 * spelled out; an unrecognized key falls back to naming the rule rather than
 * hiding it, so a new pipeline rule is never silently undocumented.
 */
export function eligibilityConditions(rule: Record<string, unknown>): string[] {
  const conditions: string[] = [];
  for (const [key, value] of Object.entries(rule)) {
    if (key === "min_observations" && typeof value === "number") {
      conditions.push(`At least ${value} comparable annual observations.`);
    } else if (key === "requires_positive" && Array.isArray(value)) {
      conditions.push(`${conceptList(value)} must be positive in that fiscal year.`);
    } else if (key === "requires_resolved" && Array.isArray(value)) {
      conditions.push(`${conceptList(value)} must be reported on the filing (not absent).`);
    } else {
      conditions.push(`Rule ${key}: ${JSON.stringify(value)}.`);
    }
  }
  return conditions;
}

function conceptList(keys: unknown[]): string {
  const labels = keys.map((key) => humanizeConceptKey(String(key)));
  if (labels.length <= 1) return labels.join("");
  return `${labels.slice(0, -1).join(", ")} and ${labels[labels.length - 1]}`;
}

function humanizeConceptKey(key: string): string {
  const label = key.replaceAll("_", " ");
  return label.charAt(0).toUpperCase() + label.slice(1);
}

// ---------------------------------------------------------------------------
// Source registry — read.source_registry_public.payload
// ---------------------------------------------------------------------------

export const sourceRegistryPayloadSchema = z.object({
  description: z.string(),
  attribution: z.string()
});

export interface SourceRegistryEntry {
  source_key: string;
  display_name: string;
  description: string;
  attribution: string;
}

/** Display names and canonical order for the published source registry. */
const SOURCE_DISPLAY: Array<{ source_key: string; display_name: string }> = [
  { source_key: "irs_990_xml", display_name: "IRS Form 990 / 990-EZ e-file" },
  { source_key: "irs_bmf", display_name: "IRS Exempt Organizations Business Master File" },
  { source_key: "irs_990n", display_name: "IRS Form 990-N (e-Postcard)" },
  { source_key: "givingtuesday", display_name: "GivingTuesday 990 Data Lake" },
  { source_key: "propublica", display_name: "ProPublica Nonprofit Explorer" }
];

/**
 * Validate registry rows and order them for display: known sources in
 * canonical order first, anything newly published after them (visible, not
 * dropped — same reasoning as the eligibility fallback above).
 */
export function mapSourceRegistry(
  rows: Array<{ source_key: string; payload: unknown }>
): SourceRegistryEntry[] {
  const entries = rows.map((row) => {
    const payload = sourceRegistryPayloadSchema.parse(row.payload);
    const display = SOURCE_DISPLAY.find((d) => d.source_key === row.source_key);
    return {
      source_key: row.source_key,
      display_name: display?.display_name ?? row.source_key,
      description: payload.description,
      attribution: payload.attribution
    };
  });
  const rank = (key: string) => {
    const index = SOURCE_DISPLAY.findIndex((d) => d.source_key === key);
    return index === -1 ? SOURCE_DISPLAY.length : index;
  };
  return entries.sort(
    (a, b) => rank(a.source_key) - rank(b.source_key) || a.source_key.localeCompare(b.source_key)
  );
}
