import { describe, expect, it } from "vitest";
import { directoryBlobSchema, type SourceRef } from "@crewgraphs/contracts";
import {
  assembleDirectory,
  assembleDirectoryEntry,
  buildDataThroughLabel,
  groupComposition,
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

describe("groupComposition", () => {
  function row(key: string, taxYear: number, value: number): FinancialSeriesRow {
    return {
      series_key: key,
      tax_year: taxYear,
      value: String(value),
      quality_state: "verified",
      is_amended: false,
      source_ref: ref(taxYear, value)
    };
  }

  const composition = groupComposition([
    row("total_revenue", 2023, 100000),
    row("total_revenue", 2024, 200000),
    row("contributions_grants", 2023, 40000),
    row("contributions_grants", 2024, 90000),
    row("membership_dues", 2024, 30000),
    row("fundraising_events_net", 2024, -5000),
    row("total_expenses", 2024, 160000),
    row("program_service_expense", 2024, 120000),
    row("salaries_benefits_total", 2023, 70000),
    row("salaries_benefits_total", 2024, 80000),
    // Published zeros in every year mean "not itemized on this club's filings".
    row("professional_fundraising_fees", 2023, 0),
    row("professional_fundraising_fees", 2024, 0),
    // A single zero year among real values is a real value and must stay.
    row("occupancy", 2023, 0),
    row("occupancy", 2024, 12000),
    // A derived-metric series must never leak into the composition tables.
    row("operating_margin", 2024, 0.2)
  ]);

  it("collects the shared ascending year axis from every composition series", () => {
    expect(composition.years).toEqual([2023, 2024]);
  });

  it("anchors each table with its total line, shares left null", () => {
    expect(composition.revenue.total?.cells[2024]?.value).toBe(200000);
    expect(composition.revenue.total?.cells[2024]?.share).toBeNull();
    expect(composition.expenses.total?.cells[2024]?.value).toBe(160000);
  });

  it("computes per-year shares against the same-year total", () => {
    const contributions = composition.revenue.groups[0].rows.find(
      (r) => r.key === "contributions_grants"
    )!;
    expect(contributions.cells[2023]?.share).toBeCloseTo(0.4);
    expect(contributions.cells[2024]?.share).toBeCloseTo(0.45);
  });

  it("keeps a negative line and its negative share", () => {
    const fundraising = composition.revenue.groups[0].rows.find(
      (r) => r.key === "fundraising_events_net"
    )!;
    expect(fundraising.cells[2024]?.value).toBe(-5000);
    expect(fundraising.cells[2024]?.share).toBeCloseTo(-0.025);
  });

  it("leaves a hole (no cell) for a year a line was not reported", () => {
    const dues = composition.revenue.groups[0].rows.find((r) => r.key === "membership_dues")!;
    expect(dues.cells[2023]).toBeUndefined();
    expect(dues.cells[2024]?.value).toBe(30000);
  });

  it("nulls the share when the year has no positive total", () => {
    const salaries = composition.expenses.groups
      .flatMap((g) => g.rows)
      .find((r) => r.key === "salaries_benefits_total")!;
    // 2023 has no total_expenses row, so the share is not computable.
    expect(salaries.cells[2023]?.share).toBeNull();
    expect(salaries.cells[2024]?.share).toBeCloseTo(0.5);
  });

  it("drops an every-year-zero line but keeps a zero year among real values", () => {
    const lineItems = composition.expenses.groups.find(
      (g) => g.label === "Notable line items"
    )!;
    expect(lineItems.rows.map((r) => r.key)).not.toContain("professional_fundraising_fees");
    const occupancy = lineItems.rows.find((r) => r.key === "occupancy")!;
    expect(occupancy.cells[2023]?.value).toBe(0);
    expect(occupancy.cells[2024]?.value).toBe(12000);
  });

  it("drops never-reported lines and empty groups, and ignores metric series", () => {
    const revenueKeys = composition.revenue.groups[0].rows.map((r) => r.key);
    expect(revenueKeys).toEqual([
      "contributions_grants",
      "membership_dues",
      "fundraising_events_net"
    ]);
    // Only program services was reported, so the functional group survives with
    // one row; management & general / fundraising never appear.
    expect(composition.expenses.groups.map((g) => g.label)).toEqual([
      "By function",
      "Notable line items"
    ]);
    expect(composition.expenses.groups[0].rows.map((r) => r.key)).toEqual([
      "program_service_expense"
    ]);
    const allKeys = [
      ...composition.revenue.groups.flatMap((g) => g.rows.map((r) => r.key)),
      ...composition.expenses.groups.flatMap((g) => g.rows.map((r) => r.key))
    ];
    expect(allKeys).not.toContain("operating_margin");
  });

  it("returns an empty composition for a filer with no composition series", () => {
    const empty = groupComposition([]);
    expect(empty.years).toEqual([]);
    expect(empty.revenue.groups).toEqual([]);
    expect(empty.expenses.total).toBeNull();
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
