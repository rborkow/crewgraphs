import { describe, expect, it } from "vitest";
import {
  directoryBlobSchema,
  orgProfilePayloadSchema,
  PAYLOAD_SCHEMA_VERSION,
  sourceRefSchema
} from "../src";

const sampleRef = {
  value: 125_000,
  unit: "USD",
  period: { tax_year: 2024, fy_end: "2025-06-30", label: "FY2024 (Jul 2024–Jun 2025)" },
  quality_state: "verified",
  source: {
    source_key: "irs_990_xml",
    form_type: "990",
    filing_id: "3f4c8a1e-0000-4000-8000-000000000001",
    source_path: "/Return/ReturnData/IRS990/CYTotalRevenueAmt",
    raw_url: "https://example.test/filing.xml",
    is_amended: false
  },
  retrieved_at: "2026-07-21T12:00:00Z",
  parser_version: "cm-2026.07.1",
  metric: null
};

describe("sourceRefSchema", () => {
  it("parses a valid SourceRef", () => {
    expect(sourceRefSchema.safeParse(sampleRef).success).toBe(true);
  });

  it("rejects an unknown unit", () => {
    expect(sourceRefSchema.safeParse({ ...sampleRef, unit: "EUR" }).success).toBe(false);
  });

  it("rejects a period without tax_year", () => {
    const { tax_year: _, ...period } = sampleRef.period;
    expect(sourceRefSchema.safeParse({ ...sampleRef, period }).success).toBe(false);
  });

  it("accepts a derived-metric ref", () => {
    const derived = {
      ...sampleRef,
      quality_state: "derived",
      source: { ...sampleRef.source, source_path: "operating_margin" },
      metric: { key: "operating_margin", version: 1 }
    };
    expect(sourceRefSchema.safeParse(derived).success).toBe(true);
  });
});

describe("orgProfilePayloadSchema", () => {
  const payload = {
    payload_schema_version: PAYLOAD_SCHEMA_VERSION,
    org_id: "3f4c8a1e-0000-4000-8000-000000000002",
    slug: "vesper-boat-club",
    header: {
      display_name: "Vesper Boat Club",
      legal_name: "Vesper Boat Club Inc",
      city: "Philadelphia",
      state: "PA",
      org_type: "private_membership_club",
      program_mix: ["masters", "open/elite"],
      website: "https://vesperboatclub.org",
      coverage_state: "990",
      blade_state: "none",
      filer_note: null
    },
    snapshot: [{ key: "total_revenue", label: "Total revenue", ref: sampleRef }],
    coverage: [
      { tax_year: 2024, fy_end: "2025-06-30", status: "990" },
      { tax_year: 2021, fy_end: null, status: "missing" }
    ],
    people: [
      {
        tax_year: 2024,
        compensated: [
          { name: "J. Smith", title: "Executive Director", avg_hours_week: 40, total_comp: 98_000, ref: sampleRef }
        ],
        volunteer_count: 12,
        ref: sampleRef
      }
    ],
    relationships: [
      { relationship_type: "boosters_for", other_org_slug: null, other_display_name: "Concord Crew", note: null }
    ],
    generated_at: "2026-07-21T12:00:00Z"
  };

  it("parses a full profile payload", () => {
    expect(orgProfilePayloadSchema.safeParse(payload).success).toBe(true);
  });

  it("rejects a snapshot fact without a ref", () => {
    const bad = { ...payload, snapshot: [{ key: "x", label: "X" }] };
    expect(orgProfilePayloadSchema.safeParse(bad).success).toBe(false);
  });

  it("rejects the wrong payload_schema_version", () => {
    expect(orgProfilePayloadSchema.safeParse({ ...payload, payload_schema_version: 99 }).success).toBe(false);
  });

  it("defaults role_flags for payloads published before capture", () => {
    const parsed = orgProfilePayloadSchema.parse(payload);
    expect(parsed.people[0].compensated[0].role_flags).toEqual([]);
  });

  it("rejects a role flag outside the Part VII checkbox set", () => {
    const person = {
      ...payload.people[0].compensated[0],
      role_flags: ["board_chair"]
    };
    const bad = {
      ...payload,
      people: [{ ...payload.people[0], compensated: [person] }]
    };
    expect(orgProfilePayloadSchema.safeParse(bad).success).toBe(false);
  });
});

describe("directoryBlobSchema", () => {
  it("parses a directory blob", () => {
    const blob = {
      snapshot_id: "3f4c8a1e-0000-4000-8000-000000000003",
      published_at: "2026-07-21T12:00:00Z",
      data_through_label: "Data through FY2024 filings",
      entries: [
        {
          org_id: "3f4c8a1e-0000-4000-8000-000000000002",
          slug: "vesper-boat-club",
          display_name: "Vesper Boat Club",
          aliases: ["Vesper", "VBC"],
          city: "Philadelphia",
          state: "PA",
          org_type: "private_membership_club",
          program_mix: ["masters"],
          peer_cohorts: ["historic-philadelphia-clubs"],
          coverage_state: "990",
          filing_years: [2021, 2022, 2023],
          latest_tax_year: 2023,
          latest_total_revenue: 1_250_000,
          fye_month: 12
        }
      ]
    };
    expect(directoryBlobSchema.safeParse(blob).success).toBe(true);
  });
});
