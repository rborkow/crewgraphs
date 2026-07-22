import { describe, expect, it } from "vitest";
import { directory } from "@/lib/directory";
import {
  buildFacets,
  entryMatchesQuery,
  normalize,
  parseQueryState,
  selectEntries,
  serializeQueryState,
  sortEntries,
  type DirectoryQueryState
} from "@/lib/directory-search";

const entries = directory.entries;
const bySlug = (slug: string) => {
  const entry = entries.find((e) => e.slug === slug);
  if (!entry) throw new Error(`fixture missing ${slug}`);
  return entry;
};

const base = (over: Partial<DirectoryQueryState> = {}): DirectoryQueryState => ({
  q: "",
  types: [],
  coverage: [],
  cohorts: [],
  sort: "name",
  ...over
});

describe("normalize", () => {
  it("folds case, punctuation, and whitespace to a bare key", () => {
    expect(normalize("Cedar-Point")).toBe("cedarpoint");
    expect(normalize("Cedar Point")).toBe("cedarpoint");
    expect(normalize("S.R.A.C.")).toBe("srac");
    expect(normalize("  ")).toBe("");
  });
});

describe("entryMatchesQuery", () => {
  it("matches on a distinctive alias, not just the display name", () => {
    const silverplain = bySlug("silverplain-river-collective");
    expect(silverplain.aliases).toContain("SRAC");
    // The letters "srac" do not appear in the display name — the hit is the alias.
    expect(normalize(silverplain.display_name).includes("srac")).toBe(false);
    expect(entryMatchesQuery(silverplain, normalize("SRAC"))).toBe(true);
  });

  it("is punctuation-insensitive", () => {
    const cedar = bySlug("cedar-point-barge-club");
    expect(entryMatchesQuery(cedar, normalize("cedar-point"))).toBe(true);
    expect(entryMatchesQuery(cedar, normalize("cedar point"))).toBe(true);
  });

  it("treats an empty query as matching everything", () => {
    expect(entryMatchesQuery(bySlug("millbrook-community-rowing"), "")).toBe(true);
  });
});

describe("selectEntries", () => {
  it("ORs values within a group", () => {
    const slugs = selectEntries(entries, base({ types: ["association", "booster_club"] })).map(
      (e) => e.slug
    );
    expect(slugs).toContain("silverplain-river-collective");
    expect(slugs).toContain("juniper-creek-rowing");
    expect(slugs).not.toContain("millbrook-community-rowing");
  });

  it("ANDs across groups", () => {
    const results = selectEntries(
      entries,
      base({ types: ["community_club"], cohorts: ["regional-community-sweep"] })
    );
    const slugs = results.map((e) => e.slug).sort();
    // Only the community clubs that also carry that cohort survive both gates.
    expect(slugs).toEqual(["bayward-community-rowing", "cobalt-reach-club"]);
  });
});

describe("sortEntries", () => {
  it("orders latest revenue high-to-low and sinks nulls to the end", () => {
    const sorted = sortEntries(entries, "revenue");
    const revenues = sorted.map((e) => e.latest_total_revenue);
    const firstNull = revenues.indexOf(null);
    // Non-null values are descending up to the first null…
    for (let i = 1; i < (firstNull === -1 ? revenues.length : firstNull); i += 1) {
      expect(revenues[i - 1]! >= revenues[i]!).toBe(true);
    }
    // …and every null is at the tail.
    if (firstNull !== -1) {
      expect(revenues.slice(firstNull).every((v) => v === null)).toBe(true);
    }
  });
});

describe("buildFacets", () => {
  it("surfaces only present values with counts", () => {
    const facets = buildFacets(entries);
    const communityClub = facets.types.find((t) => t.value === "community_club");
    expect(communityClub?.count).toBe(5);
    // Coverage keeps its canonical order.
    expect(facets.coverage[0]?.value).toBe("990");
    // Cohorts present in the fixture surface as gold-strip options.
    expect(facets.cohorts.map((c) => c.value)).toContain("regional-community-sweep");
  });
});

describe("URL codec", () => {
  it("omits defaults and round-trips through the query string", () => {
    expect(serializeQueryState(base())).toBe("");
    const state = base({ q: "row", types: ["community_club"], cohorts: ["a", "b"], sort: "revenue" });
    const round = parseQueryState(new URLSearchParams(serializeQueryState(state)));
    expect(round).toEqual(state);
  });

  it("falls back to name sort for an unknown sort value", () => {
    expect(parseQueryState(new URLSearchParams("sort=bogus")).sort).toBe("name");
  });
});
