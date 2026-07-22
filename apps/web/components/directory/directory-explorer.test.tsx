import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { fixtureDirectory } from "@/test/fixtures";
import { DirectoryExplorer } from "./directory-explorer";

function renderExplorer() {
  return render(<DirectoryExplorer entries={fixtureDirectory.entries} />);
}

const search = () => screen.getByPlaceholderText(/Search clubs, programs, boosters/);
const type = (value: string) => fireEvent.change(search(), { target: { value } });
const chip = (name: RegExp) => screen.getByRole("button", { name });

describe("DirectoryExplorer", () => {
  it("finds an organization by a distinctive alias", () => {
    renderExplorer();
    type("SRAC");
    expect(screen.getByText("Silverplain River Collective")).toBeInTheDocument();
    expect(screen.queryByText("Millbrook Community Rowing")).not.toBeInTheDocument();
  });

  it("matches with punctuation the user did not type in the name", () => {
    renderExplorer();
    type("cedar-point");
    expect(screen.getByText("Cedar Point Barge Club")).toBeInTheDocument();
  });

  it("announces the match count via an aria-live region as it changes", () => {
    renderExplorer();
    const count = screen.getByText("12 organizations");
    expect(count).toHaveAttribute("aria-live", "polite");
    type("SRAC");
    expect(screen.getByText("1 of 12 organizations")).toHaveAttribute("aria-live", "polite");
  });

  it("narrows results with a filter chip", () => {
    renderExplorer();
    fireEvent.click(chip(/Community club/));
    expect(screen.getByText("5 of 12 organizations")).toBeInTheDocument();
    expect(screen.getByText("Millbrook Community Rowing")).toBeInTheDocument();
    // A private-membership club falls out of the community-club filter.
    expect(screen.queryByText("Cedar Point Barge Club")).not.toBeInTheDocument();
  });

  it("combines a type filter and a peer-cohort filter as AND", () => {
    renderExplorer();
    fireEvent.click(chip(/Community club/));
    fireEvent.click(chip(/Regional community sweep/));
    expect(screen.getByText("2 of 12 organizations")).toBeInTheDocument();
    expect(screen.getByText("Cobalt Reach Club")).toBeInTheDocument();
    expect(screen.getByText("Bayward Community Rowing")).toBeInTheDocument();
    // A community club without the cohort is excluded by the AND.
    expect(screen.queryByText("Millbrook Community Rowing")).not.toBeInTheDocument();
  });

  it("marks an active chip with aria-pressed", () => {
    renderExplorer();
    const community = chip(/Community club/);
    expect(community).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(community);
    expect(chip(/Community club/)).toHaveAttribute("aria-pressed", "true");
  });

  it("renders a no-results state with a working clear action", () => {
    renderExplorer();
    type("zzzzzzzz");
    expect(screen.getByText(/No organizations match this view/)).toBeInTheDocument();
    const clear = screen.getByRole("button", { name: "Clear search" });
    fireEvent.click(clear);
    expect(screen.getByText("12 organizations")).toBeInTheDocument();
    expect(screen.getByText("Millbrook Community Rowing")).toBeInTheDocument();
  });

  it("links each row to its org profile route", () => {
    renderExplorer();
    const link = screen.getByRole("link", { name: /Millbrook Community Rowing/ });
    expect(link).toHaveAttribute("href", "/org/millbrook-community-rowing");

    const cedar = screen.getByRole("link", { name: /Cedar Point Barge Club/ });
    expect(cedar).toHaveAttribute("href", "/org/cedar-point-barge-club");
  });
});
