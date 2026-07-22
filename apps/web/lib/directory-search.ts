import type { DirectoryEntry } from "@crewgraphs/contracts";
import { orgTypeLabel } from "@/lib/format";

/**
 * Pure, framework-free logic for the directory experience: normalization, the
 * alias-aware matcher, facet extraction, sorting, and URL <-> state codecs.
 *
 * Everything here is a deterministic function of its inputs so the matcher and
 * URL contract can be exercised directly under test, and so the client explorer
 * and any server render agree on exactly what a shared URL means.
 */

export type SortKey = "name" | "state" | "revenue";

export interface DirectoryQueryState {
  /** Raw search text as typed (never normalized in state — the matcher normalizes). */
  q: string;
  /** Selected `org_type` enum values (OR within the group). */
  types: string[];
  /** Selected `coverage_state` enum values (OR within the group). */
  coverage: string[];
  /** Selected peer-cohort slugs (OR within the group). */
  cohorts: string[];
  sort: SortKey;
}

export const EMPTY_QUERY_STATE: DirectoryQueryState = {
  q: "",
  types: [],
  coverage: [],
  cohorts: [],
  sort: "name"
};

/**
 * Fold a string to a case- and punctuation-insensitive key. Mirrors the intent
 * of the blade hash inputs: lowercase, then drop everything that is not a letter
 * or digit — whitespace and punctuation alike. Substring matching over these
 * keys makes "Cedar Point", "cedar-point", and "cedarpoint" all equivalent, and
 * "S.R.A.C." collapse onto the alias "SRAC".
 */
export function normalize(input: string): string {
  return input.toLowerCase().replace(/[^a-z0-9]+/g, "");
}

/** The normalized haystacks a query is tested against: name, aliases, city, state. */
export function buildSearchIndex(entry: DirectoryEntry): string[] {
  const fields = [entry.display_name, ...entry.aliases, entry.city ?? "", entry.state ?? ""];
  return fields.map(normalize).filter((s) => s.length > 0);
}

/** True when the (already-normalized) query is a substring of any search field. */
export function entryMatchesQuery(entry: DirectoryEntry, normalizedQuery: string): boolean {
  if (!normalizedQuery) return true;
  return buildSearchIndex(entry).some((field) => field.includes(normalizedQuery));
}

function byName(a: DirectoryEntry, b: DirectoryEntry): number {
  return a.display_name.localeCompare(b.display_name);
}

/** Sort a copy of `entries` by the chosen key. Name is always the tiebreak. */
export function sortEntries(entries: DirectoryEntry[], sort: SortKey): DirectoryEntry[] {
  const arr = [...entries];
  switch (sort) {
    case "state":
      return arr.sort(
        (a, b) => (a.state ?? "").localeCompare(b.state ?? "") || byName(a, b)
      );
    case "revenue":
      // Highest latest revenue first; nulls (no comparable figure) always last.
      return arr.sort((a, b) => {
        const av = a.latest_total_revenue;
        const bv = b.latest_total_revenue;
        if (av === null && bv === null) return byName(a, b);
        if (av === null) return 1;
        if (bv === null) return -1;
        return bv - av || byName(a, b);
      });
    case "name":
    default:
      return arr.sort(byName);
  }
}

/** Apply the full query state — text + faceted filters + sort — to the entries. */
export function selectEntries(
  entries: DirectoryEntry[],
  state: DirectoryQueryState
): DirectoryEntry[] {
  const nq = normalize(state.q);
  const filtered = entries.filter((entry) => {
    if (!entryMatchesQuery(entry, nq)) return false;
    if (state.types.length > 0 && !state.types.includes(entry.org_type)) return false;
    if (state.coverage.length > 0 && !state.coverage.includes(entry.coverage_state)) return false;
    if (state.cohorts.length > 0 && !entry.peer_cohorts.some((c) => state.cohorts.includes(c)))
      return false;
    return true;
  });
  return sortEntries(filtered, state.sort);
}

// ---------------------------------------------------------------------------
// Labels + facets
// ---------------------------------------------------------------------------

const COVERAGE_ORDER: readonly string[] = ["990", "990ez", "990n_only", "none"];

const COVERAGE_CHIP_LABELS: Record<string, string> = {
  "990": "Form 990",
  "990ez": "Form 990-EZ",
  "990n_only": "Form 990-N",
  none: "No filings"
};

/** Chip-facing coverage label (concise; distinct from the badge's fuller wording). */
export function coverageChipLabel(state: string): string {
  return COVERAGE_CHIP_LABELS[state] ?? state;
}

/** "regional-community-sweep" -> "Regional community sweep". */
export function humanizeCohort(slug: string): string {
  const words = slug.replace(/[-_]/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export interface FacetOption {
  value: string;
  label: string;
  count: number;
}

export interface Facets {
  types: FacetOption[];
  coverage: FacetOption[];
  cohorts: FacetOption[];
}

/**
 * Extract the filter options actually present in the data. Types and cohorts are
 * alphabetized by their humanized label; coverage keeps its canonical severity
 * order (full 990 -> nothing on file).
 */
export function buildFacets(entries: DirectoryEntry[]): Facets {
  const typeCounts = new Map<string, number>();
  const coverageCounts = new Map<string, number>();
  const cohortCounts = new Map<string, number>();

  for (const entry of entries) {
    typeCounts.set(entry.org_type, (typeCounts.get(entry.org_type) ?? 0) + 1);
    coverageCounts.set(entry.coverage_state, (coverageCounts.get(entry.coverage_state) ?? 0) + 1);
    for (const cohort of entry.peer_cohorts) {
      cohortCounts.set(cohort, (cohortCounts.get(cohort) ?? 0) + 1);
    }
  }

  const types: FacetOption[] = [...typeCounts.entries()]
    .map(([value, count]) => ({ value, label: orgTypeLabel(value), count }))
    .sort((a, b) => a.label.localeCompare(b.label));

  const coverage: FacetOption[] = COVERAGE_ORDER.filter((value) => coverageCounts.has(value)).map(
    (value) => ({ value, label: coverageChipLabel(value), count: coverageCounts.get(value) ?? 0 })
  );

  const cohorts: FacetOption[] = [...cohortCounts.entries()]
    .map(([value, count]) => ({ value, label: humanizeCohort(value), count }))
    .sort((a, b) => a.label.localeCompare(b.label));

  return { types, coverage, cohorts };
}

// ---------------------------------------------------------------------------
// URL <-> state codec
// ---------------------------------------------------------------------------

/** Anything that can answer `get(name)` — URLSearchParams or Next's readonly view. */
export interface ReadableParams {
  get(name: string): string | null;
}

function parseList(params: ReadableParams, key: string): string[] {
  const raw = params.get(key);
  if (!raw) return [];
  return raw
    .split(",")
    .map((value) => value.trim())
    .filter((value) => value.length > 0);
}

/** Read directory state out of query params. Unknown values are tolerated. */
export function parseQueryState(params: ReadableParams): DirectoryQueryState {
  const sortRaw = params.get("sort");
  const sort: SortKey = sortRaw === "state" || sortRaw === "revenue" ? sortRaw : "name";
  return {
    q: params.get("q") ?? "",
    types: parseList(params, "type"),
    coverage: parseList(params, "coverage"),
    cohorts: parseList(params, "cohort"),
    sort
  };
}

/**
 * Serialize state to a canonical query string (defaults omitted). Because both
 * the "write to URL" and "read back from URL" paths run through this function,
 * comparing two serialized forms is a stable way to tell whether the URL and the
 * in-memory state already agree.
 */
export function serializeQueryState(state: DirectoryQueryState): string {
  const params = new URLSearchParams();
  const q = state.q.trim();
  if (q) params.set("q", q);
  if (state.types.length > 0) params.set("type", state.types.join(","));
  if (state.coverage.length > 0) params.set("coverage", state.coverage.join(","));
  if (state.cohorts.length > 0) params.set("cohort", state.cohorts.join(","));
  if (state.sort !== "name") params.set("sort", state.sort);
  return params.toString();
}
