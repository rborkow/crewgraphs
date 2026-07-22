import type { SourceRef } from "@crewgraphs/contracts";

/** A verified, valued SourceRef — shape mirrors packages/contracts test sample. */
export const sampleRef: SourceRef = {
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

/** A null-valued, unavailable SourceRef (the EZ-missing / not-reported case). */
export const unavailableRef: SourceRef = {
  ...sampleRef,
  value: null,
  quality_state: "unavailable",
  source: { ...sampleRef.source, source_path: "not_present_on_990ez" }
};
