import { describe, expect, it } from "vitest";
import type { DirectoryEntry, SourceRef } from "@crewgraphs/contracts";
import { formatValue } from "@/lib/format";
import {
  buildCompareCsvRows,
  buildComparisonRows,
  comparisonCellFormat,
  deriveComparisonYear,
  resolveComparisonSelection,
  serializeCompareCsv,
  type CompareSeriesRow
} from "@/lib/compare-model";
import { fixtureDirectory } from "@/test/fixtures";
import { sampleRef } from "@/test/source-ref.fixture";

function organization(slug: string): DirectoryEntry {
  const entry = fixtureDirectory.entries.find((candidate) => candidate.slug === slug);
  if (!entry) throw new Error(`missing fixture organization ${slug}`);
  return entry;
}

function seriesRow({
  org,
  key = "total_revenue",
  value = 125_000,
  quality = "verified",
  ref = sampleRef
}: {
  org: DirectoryEntry;
  key?: string;
  value?: number;
  quality?: SourceRef["quality_state"];
  ref?: SourceRef;
}): CompareSeriesRow {
  return {
    organization_id: org.org_id,
    series_key: key,
    series_version: 1,
    tax_year: 2024,
    fiscal_year_end: "2025-06-30",
    value,
    quality_state: quality,
    is_amended: false,
    source_ref: { ...ref, value, quality_state: quality }
  };
}

describe("deriveComparisonYear", () => {
  it("chooses the latest common filed TaxYr", () => {
    const result = deriveComparisonYear(
      [organization("millbrook-community-rowing"), organization("harborview-scholastic-oars")],
      null
    );
    expect(result.candidateCommonYears).toEqual([2024, 2023, 2022, 2020]);
    expect(result.selectedYear).toBe(2024);
    expect(result.usedNoCommonYearFallback).toBe(false);
  });

  it("falls back to the newest year filed by any selected organization when none is common", () => {
    const first = { ...organization("millbrook-community-rowing"), filing_years: [2022] };
    const second = { ...organization("juniper-creek-rowing"), filing_years: [2024] };
    const result = deriveComparisonYear([first, second], null);
    expect(result.candidateCommonYears).toEqual([]);
    expect(result.selectedYear).toBe(2024);
    expect(result.usedNoCommonYearFallback).toBe(true);
  });

  it("honors an explicit TaxYr even when one organization did not file it", () => {
    const result = deriveComparisonYear(
      [organization("millbrook-community-rowing"), organization("juniper-creek-rowing")],
      2023
    );
    expect(result.selectedYear).toBe(2023);
  });
});

describe("comparison selection", () => {
  it("drops unknown slugs and reports them separately", () => {
    const result = resolveComparisonSelection(fixtureDirectory.entries, [
      "millbrook-community-rowing",
      "not-a-published-org",
      "juniper-creek-rowing"
    ]);
    expect(result.organizations.map((org) => org.slug)).toEqual([
      "millbrook-community-rowing",
      "juniper-creek-rowing"
    ]);
    expect(result.unknownSlugs).toEqual(["not-a-published-org"]);
  });

  it("lets unknown slugs fall away before enforcing the four-organization limit", () => {
    const known = fixtureDirectory.entries.slice(0, 5).map((org) => org.slug);
    const result = resolveComparisonSelection(fixtureDirectory.entries, ["unknown-first", ...known]);
    expect(result.organizations).toHaveLength(4);
    expect(result.unknownSlugs).toEqual(["unknown-first"]);
    expect(result.overflowSlugs).toEqual([known[4]]);
  });
});

describe("comparison row mapping", () => {
  it("suppresses an under-review value while retaining its state and provenance", () => {
    const org = organization("millbrook-community-rowing");
    const mapped = buildComparisonRows([
      seriesRow({ org, value: 987_654, quality: "under_review" })
    ]);
    const cell = mapped.find((row) => row.key === "total_revenue")!.cells[org.org_id]!;
    expect(cell.suppressed).toBe(true);
    expect(cell.ref.value).toBeNull();
    expect(cell.ref.quality_state).toBe("under_review");
    expect(cell.ref.source.source_path).toBe(sampleRef.source.source_path);
  });

  it("formats fraction-valued derived metrics as percents", () => {
    const org = organization("millbrook-community-rowing");
    const metricRef: SourceRef = {
      ...sampleRef,
      value: 0.125,
      quality_state: "derived",
      metric: { key: "operating_margin", version: 1 },
      source: { ...sampleRef.source, source_path: "operating_margin" }
    };
    const mapped = buildComparisonRows([
      seriesRow({ org, key: "operating_margin", value: 0.125, quality: "derived", ref: metricRef })
    ]);
    const row = mapped.find((candidate) => candidate.key === "operating_margin")!;
    const cell = row.cells[org.org_id]!;
    const format = comparisonCellFormat(row, cell.ref);
    expect(format).toBe("percent");
    expect(formatValue(cell.ref.value!, format!)).toBe("12.5%");
  });
});

describe("comparison CSV", () => {
  it("serializes the fixed columns, escapes text, and excludes under-review rows", () => {
    const base = organization("millbrook-community-rowing");
    const org = { ...base, display_name: 'Millbrook Community Rowing, Inc.' };
    const rows = [
      seriesRow({ org, key: "total_revenue", value: 640_000 }),
      seriesRow({ org, key: "total_expenses", value: 600_000, quality: "under_review" })
    ];
    const csvRows = buildCompareCsvRows(rows, [org]);
    const csv = serializeCompareCsv(csvRows);

    expect(csvRows).toHaveLength(1);
    expect(csv).toContain(
      "org,series_key,label,tax_year,fiscal_year_end,value,quality_state,is_amended,source_path\r\n"
    );
    expect(csv).toContain('"Millbrook Community Rowing, Inc.",total_revenue');
    expect(csv).toContain(",640000,verified,false,");
    expect(csv).not.toContain("total_expenses");
    expect(csv.endsWith("\r\n")).toBe(true);
  });
});
