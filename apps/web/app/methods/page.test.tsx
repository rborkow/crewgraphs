import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { MetricCatalogEntry, SourceRegistryEntry } from "@/lib/methods-model";

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  )
}));

const fixtureCatalog: MetricCatalogEntry[] = [
  {
    key: "operating_margin",
    version: 1,
    label: "Operating margin",
    description: "(Total revenue − total expenses) ÷ total revenue, per fiscal year.",
    unit: "percent",
    eligibility_rule: { requires_positive: ["total_revenue"] },
    limitation: "A single year can swing on one-time gifts or capital projects; not a health grade."
  }
];

const fixtureRegistry: SourceRegistryEntry[] = [
  {
    source_key: "givingtuesday",
    display_name: "GivingTuesday 990 Data Lake",
    description: "GivingTuesday 990 Data Lake per-filing IRS XML mirror.",
    attribution:
      "GivingTuesday 990 Data Lake data is used under the Open Database License (ODbL); derivative databases remain subject to share-alike."
  }
];

vi.mock("@/lib/methods-data", () => ({
  getMetricCatalog: vi.fn(async () => fixtureCatalog),
  getSourceRegistry: vi.fn(async () => fixtureRegistry)
}));

vi.mock("@/lib/directory", () => ({
  getPublishMeta: vi.fn(async () => ({
    snapshot_id: "snapshot-1",
    published_at: "2026-07-01T00:00:00.000Z",
    data_through_label: "Data through the July 2026 publication"
  }))
}));

import MethodsPage from "./page";
import { getMetricCatalog, getSourceRegistry } from "@/lib/methods-data";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("methods page", () => {
  it("renders the methodology sections with the published catalogs", async () => {
    render(await MethodsPage());

    expect(
      screen.getByRole("heading", { name: "How these figures are made" })
    ).toBeInTheDocument();

    // Source registry entry + the standing license note with a real ODbL link.
    expect(screen.getByText("GivingTuesday 990 Data Lake")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Database License (ODbL) v1.0" })).toHaveAttribute(
      "href",
      "https://opendatacommons.org/licenses/odbl/1-0/"
    );

    // Concept table: a mapped line, its element, and a form-unavailable dash.
    expect(screen.getByText("Membership dues")).toBeInTheDocument();
    expect(screen.getAllByText("MembershipDuesAmt").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Employee count")).toBeInTheDocument();

    // Metric catalog card links to the per-metric page.
    expect(screen.getByRole("link", { name: "Operating margin" })).toHaveAttribute(
      "href",
      "/methods/operating_margin"
    );
    expect(screen.getByText(/never eligible for rankings/i)).toBeInTheDocument();

    // Publish freshness line from the snapshot.
    expect(screen.getByText("Data through the July 2026 publication.")).toBeInTheDocument();
  });

  it("renders placeholders when nothing is published yet", async () => {
    vi.mocked(getMetricCatalog).mockResolvedValueOnce([]);
    vi.mocked(getSourceRegistry).mockResolvedValueOnce([]);

    render(await MethodsPage());

    expect(
      screen.getByText("The published source registry will appear here once a snapshot is live.")
    ).toBeInTheDocument();
    expect(
      screen.getByText("The published metric catalog will appear here once a snapshot is live.")
    ).toBeInTheDocument();
  });
});
