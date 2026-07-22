import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { OrgProfilePayload } from "@crewgraphs/contracts";

// next/link needs the app-router context to be mounted; in unit tests we render
// a plain anchor so full-page renders don't require a router provider.
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: unknown; children: React.ReactNode }) => (
    <a href={typeof href === "string" ? href : "#"} {...props}>
      {children}
    </a>
  )
}));

// notFound()/permanentRedirect() throw control-flow errors that Next catches at
// the framework boundary; here we make them throw digest-carrying errors so the
// route's 404 and 308 behavior is unit-testable without the Next runtime.
vi.mock("next/navigation", () => ({
  notFound: () => {
    const error = new Error("NEXT_NOT_FOUND") as Error & { digest: string };
    error.digest = "NEXT_NOT_FOUND";
    throw error;
  },
  permanentRedirect: (url: string) => {
    const error = new Error("NEXT_REDIRECT") as Error & { digest: string };
    error.digest = `NEXT_REDIRECT;replace;${url};308;`;
    throw error;
  }
}));

// The data-access seams are mocked so the page's routing/metadata glue is
// exercised offline. provenanceKey (used by the chart wrapper) is the real
// pure helper. Component behaviors are tested by rendering the presentational
// components directly with fixture payloads, below.
vi.mock("@/lib/profile-data", async () => {
  const { provenanceKey } = await vi.importActual<typeof import("@/lib/read-model")>(
    "@/lib/read-model"
  );
  return {
    provenanceKey,
    resolveSlug: vi.fn(),
    getProfile: vi.fn(),
    getTrends: vi.fn()
  };
});
vi.mock("@/lib/directory", () => ({
  getPublishMeta: vi.fn(async () => ({
    snapshot_id: "snap",
    published_at: "2026-07-22T18:50:46.994Z",
    data_through_label: "Data through the Jul 22, 2026 publish"
  }))
}));

import OrgProfilePage, { generateMetadata } from "./page";
import { getProfile, getTrends, resolveSlug } from "@/lib/profile-data";
import { IdentityHeader } from "@/components/profile/identity-header";
import { SnapshotFacts } from "@/components/profile/snapshot-facts";
import { FinancialTrends } from "@/components/profile/financial-trends";
import { People } from "@/components/profile/people";
import { fixturePayload, fixtureTrends } from "@/test/fixtures";
import { sampleRef } from "@/test/source-ref.fixture";

afterEach(cleanup);

// ---------------------------------------------------------------------------
// Presentational components (fixture payloads as props — fully offline)
// ---------------------------------------------------------------------------

describe("profile components", () => {
  it("renders the identity header and the filer note for the booster org", () => {
    const { header, org_id } = fixturePayload("juniper-creek-rowing");
    render(<IdentityHeader header={header} orgId={org_id} />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain("Juniper Creek Rowing");
    // Whose money is shown is surfaced as a visible trust note, not a footnote.
    expect(
      screen.getByText("This booster files separately to support Bayward Community Rowing.")
    ).toBeInTheDocument();
  });

  it("shows the 990-N explainer and no charts for a 990-N-only filer", () => {
    const profile = fixturePayload("larkspur-river-adaptive");
    render(
      <FinancialTrends
        slug={profile.slug}
        coverage={profile.coverage}
        coverageState={profile.header.coverage_state}
        trends={fixtureTrends(profile.slug)}
      />
    );
    expect(screen.getByText(/This organization files Form 990-N/)).toBeInTheDocument();
    // No chart/table figure is rendered — the explainer stands in for empty charts.
    expect(screen.queryByTestId("cg-chart-region")).toBeNull();
    expect(screen.queryByTestId("cg-toggle-chart")).toBeNull();
  });

  it("opens the source drawer from a snapshot fact", () => {
    const profile = fixturePayload("millbrook-community-rowing");
    render(<SnapshotFacts snapshot={profile.snapshot} slug={profile.slug} />);

    const trigger = screen.getByRole("button", { name: /\$640,000/ });
    fireEvent.click(trigger);

    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("FY2024 (Jul 2024–Jun 2025)")).toBeInTheDocument();
    expect(
      within(dialog).getByText("/Return/ReturnData/IRS990/CYTotalRevenueAmt")
    ).toBeInTheDocument();
  });

  it("wires chart points to the source drawer and disables the missing-year point", () => {
    // Harborview (story org 4): FY2021 is a missing filing.
    const profile = fixturePayload("harborview-scholastic-oars");
    render(
      <FinancialTrends
        slug={profile.slug}
        coverage={profile.coverage}
        coverageState={profile.header.coverage_state}
        trends={fixtureTrends(profile.slug)}
      />
    );

    // The missing year is a discoverable-but-disabled 'no filing' button in
    // each chart (revenue and expenses).
    const missing = screen.getAllByRole("button", { name: /FY2021.*no filing/i });
    expect(missing.length).toBeGreaterThan(0);
    for (const button of missing) expect(button).toBeDisabled();

    // Activating a real chart point opens the drawer with that point's provenance.
    const point = screen.getByRole("button", {
      name: "FY2020 (Jul 2020–Jun 2021) Total revenue $180,000, verified"
    });
    fireEvent.click(point);

    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("FY2020 (Jul 2020–Jun 2021)")).toBeInTheDocument();
    expect(
      within(dialog).getByText("/Return/ReturnData/IRS990/CYTotalRevenueAmt")
    ).toBeInTheDocument();
  });

  it("renders compensated people rows and the volunteer aggregate line", () => {
    const people: OrgProfilePayload["people"] = [
      {
        tax_year: 2024,
        compensated: [
          {
            name: "Dana Rowe",
            title: "Executive Director",
            avg_hours_week: 40,
            role_flags: ["officer"],
            total_comp: 82000,
            ref: { ...sampleRef, value: 82000 }
          }
        ],
        volunteer_count: 12,
        ref: sampleRef
      }
    ];

    render(<People people={people} slug="millbrook-community-rowing" />);

    expect(screen.getByText("Dana Rowe")).toBeInTheDocument();
    expect(screen.getByText("Executive Director")).toBeInTheDocument();
    expect(screen.getByText("40")).toBeInTheDocument();
    // Part VII position checkboxes render as labels under the title.
    expect(screen.getByText("Officer")).toBeInTheDocument();
    // Compensation renders as a provenanced value (drawer trigger).
    expect(screen.getByRole("button", { name: /\$82,000/ })).toBeInTheDocument();
    // The many $0 volunteers collapse to one aggregate line.
    expect(
      screen.getByRole("button", { name: /12 volunteer board members, \$0 compensation/ })
    ).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Page routing + metadata glue (data seam mocked)
// ---------------------------------------------------------------------------

async function renderPage(slug: string) {
  return render(await OrgProfilePage({ params: Promise.resolve({ slug }) }));
}

describe("org profile page routing", () => {
  it("composes the page for a current slug", async () => {
    const profile = fixturePayload("millbrook-community-rowing");
    vi.mocked(resolveSlug).mockResolvedValue({ kind: "current", slug: profile.slug });
    vi.mocked(getProfile).mockResolvedValue(profile);
    vi.mocked(getTrends).mockResolvedValue(fixtureTrends(profile.slug));

    await renderPage(profile.slug);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain(
      "Millbrook Community Rowing"
    );
    // The snapshot fact renders (the figure also appears in the trend chart, so
    // there is more than one $640,000 trigger on the composed page).
    expect(screen.getAllByRole("button", { name: /\$640,000/ }).length).toBeGreaterThan(0);
    // The data-through label threaded from getPublishMeta into the sources footer.
    expect(screen.getByText(/Data through the Jul 22, 2026 publish/)).toBeInTheDocument();
  });

  it("builds the metadata title from the org name", async () => {
    vi.mocked(getProfile).mockResolvedValue(fixturePayload("millbrook-community-rowing"));
    const meta = await generateMetadata({
      params: Promise.resolve({ slug: "millbrook-community-rowing" })
    });
    expect(meta.title).toBe("Millbrook Community Rowing — CrewGraphs");
  });

  it("permanent-redirects a renamed org's old slug", async () => {
    vi.mocked(resolveSlug).mockResolvedValue({
      kind: "redirect",
      slug: "redstone-river-collective"
    });
    let error: unknown;
    try {
      await OrgProfilePage({ params: Promise.resolve({ slug: "redstone-river-club-301s" }) });
    } catch (e) {
      error = e;
    }
    const digest = (error as { digest?: string })?.digest ?? String(error);
    expect(digest).toContain("redstone-river-collective");
    expect(digest).toContain("308");
  });

  it("404s an unknown slug", async () => {
    vi.mocked(resolveSlug).mockResolvedValue({ kind: "not_found" });
    let error: unknown;
    try {
      await OrgProfilePage({ params: Promise.resolve({ slug: "not-a-real-club" }) });
    } catch (e) {
      error = e;
    }
    expect((error as { digest?: string })?.digest).toBe("NEXT_NOT_FOUND");
  });
});
