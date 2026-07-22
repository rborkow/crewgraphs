import { expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import HomePage from "./page";

it("renders the product statement", () => {
  render(<HomePage />);
  expect(screen.getByRole("heading", { level: 1 }).textContent).toContain(
    "Identity and financial context for rowing clubs"
  );
});

it("renders the fixture directory with a known organization and its coverage", () => {
  render(<HomePage />);
  expect(screen.getByText("Bayward Community Rowing")).toBeInTheDocument();
  // 990-N-only org surfaces the correct labeled badge, not a raw code.
  expect(screen.getByText("990-N filer")).toBeInTheDocument();
});
