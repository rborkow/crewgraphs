import { describe, expect, it } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { ProvenancedValue } from "./provenanced-value";
import { sampleRef, unavailableRef } from "@/test/source-ref.fixture";

describe("ProvenancedValue", () => {
  it("renders the formatted value and opens the source drawer with period + source path", () => {
    render(<ProvenancedValue refData={sampleRef} label="Total revenue" orgSlug="vesper-boat-club" />);

    const trigger = screen.getByRole("button");
    expect(trigger.textContent).toContain("$125,000");

    fireEvent.click(trigger);

    const dialog = screen.getByRole("dialog");
    // "Represents" (the period) is shown…
    expect(within(dialog).getByText("FY2024 (Jul 2024–Jun 2025)")).toBeInTheDocument();
    // …and the exact location within the filing.
    expect(within(dialog).getByText("/Return/ReturnData/IRS990/CYTotalRevenueAmt")).toBeInTheDocument();
    // …and the correction link carries org + period context.
    const correction = within(dialog).getByRole("link", { name: "Report a correction" });
    expect(correction.getAttribute("href")).toContain("org=vesper-boat-club");
    expect(correction.getAttribute("href")).toContain("period=2024");
  });

  it("renders the labeled state for a null value, never 0 or blank", () => {
    render(<ProvenancedValue refData={unavailableRef} label="Cash & savings" />);
    const trigger = screen.getByRole("button");
    expect(trigger.textContent).toContain("Unavailable");
    expect(trigger.textContent).not.toContain("0");
    expect(trigger.textContent).not.toContain("$");
  });

  it("shows an inline quality chip for non-verified values", () => {
    const derived = {
      ...sampleRef,
      value: 0.082,
      quality_state: "derived" as const,
      source: { ...sampleRef.source, source_path: "operating_margin" },
      metric: { key: "operating_margin", version: 1 }
    };
    render(<ProvenancedValue refData={derived} format="percent" label="Operating margin" />);
    const trigger = screen.getByRole("button");
    expect(trigger.textContent).toContain("8.2%");
    expect(trigger.textContent).toContain("Derived");
  });
});
