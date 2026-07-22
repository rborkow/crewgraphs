import { describe, expect, it } from "vitest";
import { sourceRefSchema } from "../src";

const sample = {
  value: 125_000,
  unit: "USD",
  period: { fy_end: "2025-12-31", label: "FY 2025" },
  quality_state: "verified",
  source: {
    source_key: "irs-efile",
    form_type: "990",
    filing_id: "202512345678901234",
    source_path: "Return/Revenue",
    raw_url: "https://example.test/filing.xml"
  },
  retrieved_at: "2026-07-21T12:00:00Z",
  parser_version: "0.0.0",
  metric: { key: "total_revenue", version: 0 }
};

describe("sourceRefSchema", () => {
  it("parses a valid SourceRef", () => {
    expect(sourceRefSchema.safeParse(sample).success).toBe(true);
  });

  it("rejects an invalid SourceRef", () => {
    expect(sourceRefSchema.safeParse({ ...sample, unit: "EUR" }).success).toBe(false);
  });
});
