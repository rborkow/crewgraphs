import { describe, expect, it } from "vitest";
import { directoryBlobSchema, type SourceRef } from "@crewgraphs/contracts";
import {
  assembleDirectory,
  assembleDirectoryEntry,
  buildDataThroughLabel,
  groupTrends,
  mapProfilePayload,
  resolveFromRows,
  type DirectoryJoinRow,
  type FinancialSeriesRow
} from "@/lib/read-model";
import { formatDate } from "@/lib/format";
import { fixturePayload, fixtureSeriesRows } from "@/test/fixtures";
import { sampleRef } from "@/test/source-ref.fixture";

// A full, valid SourceRef for a given fiscal year / value — mirrors what the
// read model stores in org_financial_series.source_ref.
function ref(taxYear: number, value: number | null, unit: "USD" | "count" = "USD"): SourceRef {
  return {
    ...sampleRef,
    value,
    unit,
    period: {
      tax_year: taxYear,
      fy_end: `${taxYear + 1}-06-30`,
      label: `FY${taxYear} (Jul ${taxYear}–Jun ${taxYear + 1})`
    }
  };
}

describe("mapProfilePayload", () => {
  it("parses a valid published payload", () => {
    const payload = mapProfilePayload(fixturePayload("millbrook-community-rowing"));
    expect(payload.slug).toBe("millbrook-community-rowing");
  });

  it("throws when a payload violates the contract", () => {
    expect(() => mapProfilePayload({ slug: "x" })).toThrow();
  });
});

describe("groupTrends (fixture rows)", () => {
  const trends = groupTrends(
    fixtureSeriesRows("harborview-scholastic-oars"),
    fixturePayload("harborview-scholastic-oars").coverage
  );

  it("charts revenue and expenses as multi-year lines", () => {
    expect(trends.charts.map((c) => c.series.key)).toEqual(["total_revenue", "total_expenses"]);
    for (const chart of trends.charts) expect(chart.kind).toBe("line");
  });

  it("keeps the missing fiscal year as a null point and names it in the summary", () => {
    const revenue = trends.charts.find((c) => c.series.key === "total_revenue")!;
    const fy2021 = revenue.series.points.find((p) => p.tax_year === 2021)!;
    expect(fy2021.value).toBeNull();
    expect(revenue.ariaSummary).toContain("FY2021 missing");
    // The first filed year keeps its real value.
    expect(revenue.series.points.find((p) => p.tax_year === 2020)!.value).toBe(180000);
  });

  it("keys provenance by series_key::tax_year", () => {
    expect(trends.provenance["total_revenue::2020"]?.value).toBe(180000);
    expect(trends.provenance["total_revenue::2021"]).toBeDefined();
  });
});

describe("groupTrends (live-shaped rows)", () => {
  // The published series omits missing years entirely and returns numeric
  // columns as strings; the grouper must coerce values and inject the gap.
  const rows: FinancialSeriesRow[] = [
    { series_key: "total_revenue", tax_year: 2020, value: "301701.00", quality_state: "verified", is_amended: false, source_ref: ref(2020, 301701) },
    { series_key: "total_revenue", tax_year: 2022, value: "413528.00", quality_state: "verified", is_amended: false, source_ref: ref(2022, 413528) },
    { series_key: "total_revenue", tax_year: 2023, value: "409655.00", quality_state: "verified", is_amended: false, source_ref: ref(2023, 409655) },
    { series_key: "total_revenue", tax_year: 2024, value: "438872.00", quality_state: "verified", is_amended: false, source_ref: ref(2024, 438872) }
  ];
  const coverage = [
    { tax_year: 2020, fy_end: "2021-06-30", status: "990" as const },
    { tax_year: 2021, fy_end: null, status: "missing" as const },
    { tax_year: 2022, fy_end: "2023-06-30", status: "990" as const },
    { tax_year: 2023, fy_end: "2024-06-30", status: "990" as const },
    { tax_year: 2024, fy_end: "2025-06-30", status: "990" as const }
  ];
  const trends = groupTrends(rows, coverage);

  it("coerces string values to numbers", () => {
    const revenue = trends.charts[0];
    expect(revenue.series.points.find((p) => p.tax_year === 2024)!.value).toBe(438872);
  });

  it("injects a null point for the interior missing coverage year", () => {
    const revenue = trends.charts[0];
    const years = revenue.series.points.map((p) => p.tax_year);
    expect(years).toEqual([2020, 2021, 2022, 2023, 2024]);
    const gap = revenue.series.points.find((p) => p.tax_year === 2021)!;
    expect(gap.value).toBeNull();
    expect(gap.quality_state).toBe("unavailable");
    expect(gap.label).toBe("FY2021");
  });

  it("only charts concept keys that are present", () => {
    expect(trends.charts).toHaveLength(1);
  });
});

describe("groupTrends edge cases", () => {
  it("returns no charts for a 990-N-only filer with no concept series", () => {
    const trends = groupTrends(
      fixtureSeriesRows("larkspur-river-adaptive"),
      fixturePayload("larkspur-river-adaptive").coverage
    );
    expect(trends.charts).toHaveLength(0);
  });

  it("renders a single filed year as a bar", () => {
    const rows: FinancialSeriesRow[] = [
      { series_key: "total_revenue", tax_year: 2024, value: 46000, quality_state: "verified", is_amended: false, source_ref: ref(2024, 46000) }
    ];
    const coverage = [{ tax_year: 2024, fy_end: "2025-06-30", status: "990" as const }];
    const trends = groupTrends(rows, coverage);
    expect(trends.charts[0].kind).toBe("bar");
    expect(trends.charts[0].series.points).toHaveLength(1);
  });
});

describe("resolveFromRows", () => {
  const directoryRows = [
    { organization_id: "org-1", slug: "vesper-boat-club" },
    { organization_id: "org-2", slug: "marin-rowing-association" }
  ];
  const historyRows = [
    { slug: "vesper-boat-club", org_id: "org-1", is_current: true },
    { slug: "marin-rowing-association", org_id: "org-2", is_current: true },
    { slug: "old-vesper", org_id: "org-1", is_current: false }
  ];

  it("resolves a current slug to its page", () => {
    expect(resolveFromRows("vesper-boat-club", directoryRows, historyRows)).toEqual({
      kind: "current",
      slug: "vesper-boat-club"
    });
  });

  it("redirects a renamed org's old slug to its current slug", () => {
    expect(resolveFromRows("old-vesper", directoryRows, historyRows)).toEqual({
      kind: "redirect",
      slug: "vesper-boat-club"
    });
  });

  it("404s an unknown slug", () => {
    expect(resolveFromRows("not-a-real-club", directoryRows, historyRows)).toEqual({
      kind: "not_found"
    });
  });
});

describe("assembleDirectoryEntry", () => {
  const payload = fixturePayload("millbrook-community-rowing");
  const row: DirectoryJoinRow = {
    organization_id: payload.org_id,
    slug: "millbrook-community-rowing",
    display_name: "Millbrook Community Rowing",
    aliases: ["Millbrook Rowing", "MCR"],
    coverage_state: "990",
    fye_month: 6,
    payload
  };

  it("joins header facts and derives filing years / latest revenue", () => {
    const entry = assembleDirectoryEntry(row);
    expect(entry.org_type).toBe("community_club");
    expect(entry.city).toBe("Millbrook");
    expect(entry.filing_years).toEqual([2020, 2021, 2022, 2023, 2024]);
    expect(entry.latest_tax_year).toBe(2024);
    expect(entry.latest_total_revenue).toBe(640000);
    expect(entry.peer_cohorts).toEqual([]);
  });

  it("yields null latest revenue for a 990-N-only filer", () => {
    const larkspur = fixturePayload("larkspur-river-adaptive");
    const entry = assembleDirectoryEntry({
      organization_id: larkspur.org_id,
      slug: "larkspur-river-adaptive",
      display_name: "Larkspur River Adaptive",
      aliases: [],
      coverage_state: "990n_only",
      fye_month: null,
      payload: larkspur
    });
    expect(entry.latest_total_revenue).toBeNull();
    expect(entry.filing_years).toEqual([2022, 2023, 2024]);
  });
});

describe("buildDataThroughLabel", () => {
  const iso = "2026-07-22T18:50:46.994Z";

  it("formats the publish date from a Date", () => {
    expect(buildDataThroughLabel(new Date(iso))).toBe(`Data through the ${formatDate(iso)} publish`);
  });

  it("accepts an ISO string too", () => {
    expect(buildDataThroughLabel(iso)).toBe(`Data through the ${formatDate(iso)} publish`);
  });
});

describe("assembleDirectory", () => {
  it("builds a contract-valid blob sorted by display name", () => {
    const a = fixturePayload("millbrook-community-rowing");
    const b = fixturePayload("bayward-community-rowing");
    const rows: DirectoryJoinRow[] = [
      { organization_id: a.org_id, slug: a.slug, display_name: "Millbrook Community Rowing", aliases: [], coverage_state: "990", fye_month: 6, payload: a },
      { organization_id: b.org_id, slug: b.slug, display_name: "Bayward Community Rowing", aliases: [], coverage_state: "990", fye_month: 6, payload: b }
    ];
    const blob = assembleDirectory(
      { snapshot_id: "00000000-0000-4000-8000-000000000001", updated_at: new Date("2026-07-22T18:50:46.994Z") },
      rows
    );
    // Parses cleanly through the contract and is name-sorted.
    directoryBlobSchema.parse(blob);
    expect(blob.entries.map((e) => e.display_name)).toEqual([
      "Bayward Community Rowing",
      "Millbrook Community Rowing"
    ]);
  });
});
