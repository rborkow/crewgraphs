import { z } from "zod";

/**
 * CrewGraphs cross-tier contracts, v1.
 *
 * These schemas are the shared boundary between the Python ingestion side
 * (which publishes read-model rows and validates its jsonb payloads against
 * the exported JSON Schemas) and the web tier (which renders exclusively
 * through them — `ProvenancedValue` requires a full SourceRef, making
 * provenance-less numbers unrepresentable).
 *
 * Version discipline: additive changes bump PAYLOAD_SCHEMA_VERSION; breaking
 * changes require a new exported schema file alongside the old one until the
 * published snapshot has been rebuilt.
 */

export const PAYLOAD_SCHEMA_VERSION = 1;

// ---------------------------------------------------------------------------
// Shared enums (mirror db enums — see db/schema.sql)
// ---------------------------------------------------------------------------

export const qualityStateSchema = z.enum([
  "verified",
  "derived",
  "partial",
  "unavailable",
  "under_review"
]);

export const formTypeSchema = z.enum(["990", "990EZ", "990N"]);

export const coverageStateSchema = z.enum(["990", "990ez", "990n_only", "none"]);

export const filingCoverageStatusSchema = z.enum([
  "990",
  "990ez",
  "990n",
  "amended",
  "missing",
  "not_yet_expected"
]);

export const orgTypeSchema = z.enum([
  "community_club",
  "private_membership_club",
  "scholastic_program",
  "collegiate_varsity",
  "collegiate_club",
  "university_support_foundation",
  "booster_club",
  "adaptive_program",
  "association",
  "governing_body",
  "other"
]);

// ---------------------------------------------------------------------------
// SourceRef — the provenance atom (PRD §14 minimum-provenance contract)
// ---------------------------------------------------------------------------

export const sourceRefSchema = z.object({
  value: z.number().nullable(),
  unit: z.enum(["USD", "count"]),
  period: z.object({
    /** IRS TaxYr from the return header — the comparison axis (spike Q7). */
    tax_year: z.number().int(),
    /** Fiscal year end date; differs from tax_year+1 for non-December FYE. */
    fy_end: z.iso.date(),
    /** Human label, e.g. "FY2024 (Jul 2023–Jun 2024)". */
    label: z.string()
  }),
  quality_state: qualityStateSchema,
  source: z.object({
    /** db source_type enum value, e.g. "irs_990_xml". */
    source_key: z.string(),
    form_type: formTypeSchema,
    filing_id: z.string(),
    /** Exact XPath within the return for concept values; concept key for derived. */
    source_path: z.string(),
    /** Link to the raw filing object when publicly addressable. */
    raw_url: z.url().nullable(),
    /** Set when this value comes from an amended return. */
    is_amended: z.boolean().default(false)
  }),
  retrieved_at: z.iso.datetime(),
  /** Concept-map / parser version, e.g. "cm-2026.07.1". */
  parser_version: z.string(),
  /** Present only for derived metrics; null for raw concepts. */
  metric: z
    .object({
      key: z.string(),
      version: z.number().int()
    })
    .nullable()
});

export type SourceRef = z.infer<typeof sourceRefSchema>;

// ---------------------------------------------------------------------------
// Profile payload — read.org_profile.payload
// ---------------------------------------------------------------------------

/** A displayed fact: label + fully-provenanced value. */
export const provenancedFactSchema = z.object({
  key: z.string(),
  label: z.string(),
  ref: sourceRefSchema
});

export const profileHeaderSchema = z.object({
  display_name: z.string(),
  legal_name: z.string().nullable(),
  city: z.string().nullable(),
  state: z.string().nullable(),
  org_type: orgTypeSchema,
  program_mix: z.array(z.string()),
  website: z.url().nullable(),
  coverage_state: coverageStateSchema,
  /** Blade art display gate; render neutral placeholder unless "licensed" or "club_supplied". */
  blade_state: z.enum(["none", "linked_only", "permission_requested", "licensed", "club_supplied"]),
  /**
   * Racing identity ≠ legal filer is the norm (spike: 4 of 10). When set,
   * the profile must say whose money is shown.
   */
  filer_note: z.string().nullable()
});

/** Form 990 Part VII position checkboxes (990-EZ rows carry none). */
export const personRoleFlagSchema = z.enum([
  "individual_trustee_or_director",
  "officer",
  "key_employee",
  "highest_compensated_employee",
  "former_officer_director_trustee"
]);

/** One officer/key-employee row. Spike display rule: only comp > 0 rows are listed. */
export const compensatedPersonSchema = z.object({
  name: z.string(),
  title: z.string().nullable(),
  avg_hours_week: z.number().nullable(),
  /** Optional-with-default so payloads published before capture stay valid. */
  role_flags: z.array(personRoleFlagSchema).default([]),
  total_comp: z.number(),
  ref: sourceRefSchema
});

export const peopleYearSchema = z.object({
  tax_year: z.number().int(),
  compensated: z.array(compensatedPersonSchema),
  /** "N volunteer board members, $0 compensation" aggregate. */
  volunteer_count: z.number().int(),
  ref: sourceRefSchema
});

export const filingCoverageEntrySchema = z.object({
  tax_year: z.number().int(),
  fy_end: z.iso.date().nullable(),
  status: filingCoverageStatusSchema
});

export const orgProfilePayloadSchema = z.object({
  payload_schema_version: z.literal(PAYLOAD_SCHEMA_VERSION),
  org_id: z.uuid(),
  slug: z.string(),
  header: profileHeaderSchema,
  /** 4–6 facts; never a composite score. */
  snapshot: z.array(provenancedFactSchema).min(1).max(8),
  /** Drives missing-vs-zero and 990-N states deterministically (UX-03). */
  coverage: z.array(filingCoverageEntrySchema),
  people: z.array(peopleYearSchema),
  /** Relationships worth rendering, e.g. "boosters_for Concord Crew". */
  relationships: z.array(
    z.object({
      relationship_type: z.string(),
      other_org_slug: z.string().nullable(),
      other_display_name: z.string(),
      note: z.string().nullable()
    })
  ),
  generated_at: z.iso.datetime()
});

export type OrgProfilePayload = z.infer<typeof orgProfilePayloadSchema>;

// ---------------------------------------------------------------------------
// Directory blob — the KV-served client search index
// ---------------------------------------------------------------------------

export const directoryEntrySchema = z.object({
  org_id: z.uuid(),
  slug: z.string(),
  display_name: z.string(),
  aliases: z.array(z.string()),
  city: z.string().nullable(),
  state: z.string().nullable(),
  org_type: orgTypeSchema,
  program_mix: z.array(z.string()),
  peer_cohorts: z.array(z.string()),
  coverage_state: coverageStateSchema,
  filing_years: z.array(z.number().int()),
  latest_tax_year: z.number().int().nullable(),
  latest_total_revenue: z.number().nullable(),
  fye_month: z.number().int().min(1).max(12).nullable()
});

export const directoryBlobSchema = z.object({
  snapshot_id: z.uuid(),
  published_at: z.iso.datetime(),
  /** Represented-data recency, distinct from published_at (source-lag rule). */
  data_through_label: z.string(),
  entries: z.array(directoryEntrySchema)
});

export type DirectoryEntry = z.infer<typeof directoryEntrySchema>;
export type DirectoryBlob = z.infer<typeof directoryBlobSchema>;
