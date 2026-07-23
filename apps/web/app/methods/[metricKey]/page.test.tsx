import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { MetricCatalogEntry } from "@/lib/methods-model";

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  )
}));

vi.mock("next/navigation", () => ({
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  })
}));

const fixtureCatalog: MetricCatalogEntry[] = [
  {
    key: "revenue_cagr",
    version: 1,
    label: "Revenue growth (CAGR)",
    description:
      "Compound annual growth rate between the earliest and latest comparable total-revenue observations in the selected window.",
    unit: "percent",
    eligibility_rule: { min_observations: 3 },
    limitation:
      "Requires at least three comparable annual filings; window boundaries are disclosed with the value."
  }
];

vi.mock("@/lib/methods-data", () => ({
  getMetricCatalog: vi.fn(async () => fixtureCatalog)
}));

import MetricPage from "./page";
import { notFound } from "next/navigation";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("metric definition page", () => {
  it("renders a published metric definition in full", async () => {
    render(await MetricPage({ params: Promise.resolve({ metricKey: "revenue_cagr" }) }));

    expect(screen.getByRole("heading", { name: "Revenue growth (CAGR)" })).toBeInTheDocument();
    expect(screen.getByText(/version 1/)).toBeInTheDocument();
    expect(screen.getByText("At least 3 comparable annual observations.")).toBeInTheDocument();
    expect(screen.getByText(/window boundaries are disclosed/)).toBeInTheDocument();
  });

  it("404s for a metric key that is not in the published catalog", async () => {
    await expect(
      MetricPage({ params: Promise.resolve({ metricKey: "club_score" }) })
    ).rejects.toThrow("NEXT_NOT_FOUND");
    expect(notFound).toHaveBeenCalled();
  });
});
