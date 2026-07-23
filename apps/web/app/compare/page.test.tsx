import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fixtureDirectory } from "@/test/fixtures";

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  )
}));

vi.mock("@/lib/directory", () => ({
  getDirectory: vi.fn(async () => fixtureDirectory)
}));

vi.mock("@/lib/compare-data", () => ({
  getCompareSeries: vi.fn(async () => [])
}));

import ComparePage from "./page";
import { getCompareSeries } from "@/lib/compare-data";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

async function renderPage(searchParams: Record<string, string | undefined>) {
  return render(await ComparePage({ searchParams: Promise.resolve(searchParams) }));
}

describe("compare page", () => {
  it("shows the selection empty state with fewer than two valid organizations", async () => {
    await renderPage({ orgs: "millbrook-community-rowing" });
    expect(screen.getByText("Choose at least two organizations")).toBeInTheDocument();
    expect(getCompareSeries).not.toHaveBeenCalled();
  });

  it("drops an unknown slug with a visible notice", async () => {
    await renderPage({ orgs: "millbrook-community-rowing,unknown-club" });
    expect(screen.getByRole("status")).toHaveTextContent(
      "Unknown organizations were left out: unknown-club."
    );
    expect(screen.getByText("Choose at least two organizations")).toBeInTheDocument();
  });

  it("keeps an organization without the explicit year and renders unavailable cells", async () => {
    await renderPage({
      orgs: "millbrook-community-rowing,juniper-creek-rowing",
      fy: "2023"
    });
    expect(screen.getByText("Millbrook Community Rowing")).toBeInTheDocument();
    expect(screen.getByText("Juniper Creek Rowing")).toBeInTheDocument();
    expect(screen.getAllByText("No filing for this TaxYr").length).toBeGreaterThan(0);
    expect(getCompareSeries).toHaveBeenCalledWith(
      fixtureDirectory.snapshot_id,
      expect.arrayContaining([
        expect.any(String),
        expect.any(String)
      ]),
      2023
    );
  });
});
