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
// route's 404 and 301 behavior is unit-testable without the Next runtime.
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

import OrgProfilePage, { generateMetadata, generateStaticParams } from "./page";
import { getProfile, getRouteSlugs, resolveSlug, SLUG_HISTORY } from "@/lib/profile-data";
import { SnapshotFacts } from "@/components/profile/snapshot-facts";
import { People } from "@/components/profile/people";
import { sampleRef } from "@/test/source-ref.fixture";

afterEach(cleanup);

async function renderPage(slug: string) {
  return render(await OrgProfilePage({ params: Promise.resolve({ slug }) }));
}

describe("org profile page", () => {
  it("renders the identity header and the filer note for the booster org", async () => {
    await renderPage("juniper-creek-rowing");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain("Juniper Creek Rowing");
    // Whose money is shown is surfaced as a visible trust note, not a footnote.
    expect(
      screen.getByText("This booster files separately to support Bayward Community Rowing.")
    ).toBeInTheDocument();
  });

  it("shows the 990-N explainer and no charts for a 990-N-only filer", async () => {
    await renderPage("larkspur-river-adaptive");
    expect(screen.getByText(/This organization files Form 990-N/)).toBeInTheDocument();
    // No chart/table figure is rendered — the explainer stands in for empty charts.
    expect(screen.queryByTestId("cg-chart-region")).toBeNull();
    expect(screen.queryByTestId("cg-toggle-chart")).toBeNull();
  });

  it("opens the source drawer from a snapshot fact", () => {
    const profile = getProfile("millbrook-community-rowing")!;
    render(<SnapshotFacts snapshot={profile.snapshot} slug={profile.slug} />);

    const trigger = screen.getByRole("button", { name: /\$640,000/ });
    fireEvent.click(trigger);

    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("FY2024 (Jul 2024–Jun 2025)")).toBeInTheDocument();
    expect(
      within(dialog).getByText("/Return/ReturnData/IRS990/CYTotalRevenueAmt")
    ).toBeInTheDocument();
  });

  it("wires chart points to the source drawer and disables the missing-year point", async () => {
    // Harborview (story org 4): FY2021 is a missing filing.
    await renderPage("harborview-scholastic-oars");

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
    // Compensation renders as a provenanced value (drawer trigger).
    expect(screen.getByRole("button", { name: /\$82,000/ })).toBeInTheDocument();
    // The many $0 volunteers collapse to one aggregate line.
    expect(
      screen.getByRole("button", { name: /12 volunteer board members, \$0 compensation/ })
    ).toBeInTheDocument();
  });

  it("builds the metadata title from the org name", async () => {
    const meta = await generateMetadata({
      params: Promise.resolve({ slug: "millbrook-community-rowing" })
    });
    expect(meta.title).toBe("Millbrook Community Rowing — CrewGraphs");
  });
});

describe("renamed-org slug history", () => {
  it("maps a renamed org's old slug to its current slug", () => {
    expect(SLUG_HISTORY["redstone-river-club-301s"]).toBe("redstone-river-collective");
    expect(resolveSlug("redstone-river-club-301s")).toEqual({
      kind: "redirect",
      slug: "redstone-river-collective"
    });
    expect(resolveSlug("redstone-river-collective")).toEqual({
      kind: "current",
      slug: "redstone-river-collective"
    });
    // generateStaticParams must include the old slug so the route can 301 it.
    expect(getRouteSlugs()).toContain("redstone-river-club-301s");
    expect(generateStaticParams()).toContainEqual({ slug: "redstone-river-club-301s" });
  });

  it("permanent-redirects the old slug at the route level", async () => {
    let error: unknown;
    try {
      await OrgProfilePage({ params: Promise.resolve({ slug: "redstone-river-club-301s" }) });
    } catch (e) {
      error = e;
    }
    expect(error).toBeDefined();
    const digest = (error as { digest?: string })?.digest ?? String(error);
    expect(digest).toContain("redstone-river-collective");
  });

  it("404s an unknown slug", async () => {
    let error: unknown;
    try {
      await OrgProfilePage({ params: Promise.resolve({ slug: "not-a-real-club" }) });
    } catch (e) {
      error = e;
    }
    expect(error).toBeDefined();
  });
});
