import { expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { fixtureDirectory } from "@/test/fixtures";

// The page reads the directory live; here the data seam is mocked with the
// offline fixture blob so the async server component renders without a
// connection. `render(await HomePage())` resolves the RSC to its element tree.
vi.mock("@/lib/directory", () => ({
  getDirectory: vi.fn(async () => fixtureDirectory)
}));

import HomePage from "./page";

it("renders the product statement", async () => {
  render(await HomePage());
  expect(screen.getByRole("heading", { level: 1 }).textContent).toContain(
    "Identity and financial context for rowing clubs"
  );
});

it("renders the directory with a known organization and its coverage", async () => {
  render(await HomePage());
  expect(screen.getByText("Bayward Community Rowing")).toBeInTheDocument();
  // 990-N-only org surfaces the correct labeled badge, not a raw code.
  expect(screen.getByText("990-N filer")).toBeInTheDocument();
});
