import { expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import HomePage from "./page";

it("renders the CrewGraphs coming soon message", () => {
  render(<HomePage />);

  expect(screen.getByRole("heading", { name: "CrewGraphs — rowing club reference. Coming soon." })).toBeInTheDocument();
});
