import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { QualityChip, type QualityState } from "./quality-chip";

const CASES: Array<[QualityState, string]> = [
  ["verified", "Verified"],
  ["derived", "Derived"],
  ["partial", "Partial"],
  ["unavailable", "Unavailable"],
  ["under_review", "Under review"]
];

describe("QualityChip", () => {
  it.each(CASES)("renders a text label for %s (never colour alone)", (state, label) => {
    const { unmount } = render(<QualityChip state={state} />);
    expect(screen.getByText(label)).toBeInTheDocument();
    unmount();
  });

  it("tags the state for styling hooks", () => {
    const { container } = render(<QualityChip state="under_review" />);
    expect(container.querySelector('[data-quality-state="under_review"]')).not.toBeNull();
  });
});
