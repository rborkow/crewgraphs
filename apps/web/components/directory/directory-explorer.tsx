"use client";

import { useCallback, useEffect, useId, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { DirectoryEntry } from "@crewgraphs/contracts";
import {
  buildFacets,
  parseQueryState,
  selectEntries,
  serializeQueryState,
  type DirectoryQueryState,
  type SortKey
} from "@/lib/directory-search";
import { FilterChip } from "./filter-chip";
import { OrgRow } from "./org-row";

type FilterGroup = "types" | "coverage" | "cohorts";
type History = "push" | "replace";

const SORT_OPTIONS: ReadonlyArray<{ value: SortKey; label: string }> = [
  { value: "name", label: "Name (A–Z)" },
  { value: "state", label: "State" },
  { value: "revenue", label: "Latest revenue" }
];

export interface DirectoryExplorerProps {
  entries: DirectoryEntry[];
}

/**
 * The directory-first home surface: prominent search, quiet facet + cohort
 * toggles, a sort control, and the row list. Filtering runs entirely on the
 * client so results update as you type, while every change is mirrored into the
 * URL (?q=&type=&coverage=&cohort=&sort=) so a view is shareable and the
 * back/forward buttons restore it.
 */
export function DirectoryExplorer({ entries }: DirectoryExplorerProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Seed from the URL so a shared link renders its filtered view on first paint.
  const [state, setState] = useState<DirectoryQueryState>(() => parseQueryState(searchParams));

  // Reconcile external navigation (back/forward, or any URL change we didn't
  // originate) back into state. The equality guard means our own writes — which
  // set state first, then push — never round-trip into a redundant update.
  useEffect(() => {
    const fromUrl = parseQueryState(searchParams);
    setState((prev) =>
      serializeQueryState(prev) === serializeQueryState(fromUrl) ? prev : fromUrl
    );
  }, [searchParams]);

  const commit = useCallback(
    (next: DirectoryQueryState, history: History) => {
      setState(next);
      const qs = serializeQueryState(next);
      const url = qs ? `${pathname}?${qs}` : pathname;
      if (history === "push") router.push(url, { scroll: false });
      else router.replace(url, { scroll: false });
    },
    [router, pathname]
  );

  const facets = useMemo(() => buildFacets(entries), [entries]);
  const results = useMemo(() => selectEntries(entries, state), [entries, state]);
  const total = entries.length;

  const hasActiveFilters =
    state.q.trim().length > 0 ||
    state.types.length > 0 ||
    state.coverage.length > 0 ||
    state.cohorts.length > 0;

  const setQuery = useCallback(
    (q: string) => {
      // Typing shouldn't spam history — mirror the text with replace().
      commit({ ...state, q }, "replace");
    },
    [commit, state]
  );

  const toggle = useCallback(
    (group: FilterGroup, value: string) => {
      const current = state[group];
      const next = current.includes(value)
        ? current.filter((v) => v !== value)
        : [...current, value];
      commit({ ...state, [group]: next }, "push");
    },
    [commit, state]
  );

  const setSort = useCallback(
    (sort: SortKey) => {
      commit({ ...state, sort }, "push");
    },
    [commit, state]
  );

  const clearAll = useCallback(() => {
    commit({ q: "", types: [], coverage: [], cohorts: [], sort: state.sort }, "push");
  }, [commit, state.sort]);

  const searchId = useId();
  const sortId = useId();
  const countLabel =
    results.length === total
      ? `${total} organizations`
      : `${results.length} of ${total} organizations`;

  return (
    <section className="py-8 sm:py-10">
      {/* Search */}
      <div className="relative">
        <label htmlFor={searchId} className="sr-only">
          Search organizations
        </label>
        <SearchGlyph className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-faint" />
        <input
          id={searchId}
          type="search"
          inputMode="search"
          autoComplete="off"
          spellCheck={false}
          value={state.q}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search clubs, programs, boosters…"
          className="w-full rounded-sm border border-mist bg-paper py-3 pl-11 pr-10 text-base text-river placeholder:text-faint focus-visible:border-buoy"
        />
        {state.q ? (
          <button
            type="button"
            onClick={() => setQuery("")}
            aria-label="Clear search text"
            className="absolute right-2 top-1/2 flex size-7 -translate-y-1/2 items-center justify-center rounded-sm text-faint transition-colors hover:text-river"
          >
            <CloseGlyph className="size-4" />
          </button>
        ) : null}
      </div>

      {/* Facet toggles */}
      <div className="mt-5 flex flex-col gap-3">
        {facets.types.length > 0 ? (
          <FilterRow label="Type">
            {facets.types.map((facet) => (
              <FilterChip
                key={facet.value}
                active={state.types.includes(facet.value)}
                onToggle={() => toggle("types", facet.value)}
                count={facet.count}
              >
                {facet.label}
              </FilterChip>
            ))}
          </FilterRow>
        ) : null}

        {facets.coverage.length > 0 ? (
          <FilterRow label="Coverage">
            {facets.coverage.map((facet) => (
              <FilterChip
                key={facet.value}
                active={state.coverage.includes(facet.value)}
                onToggle={() => toggle("coverage", facet.value)}
                count={facet.count}
              >
                {facet.label}
              </FilterChip>
            ))}
          </FilterRow>
        ) : null}
      </div>

      {/* Peer cohorts */}
      {facets.cohorts.length > 0 ? (
        <FilterRow label="Peer cohorts" className="mt-3">
          {facets.cohorts.map((facet) => (
            <FilterChip
              key={facet.value}
              tone="gold"
              active={state.cohorts.includes(facet.value)}
              onToggle={() => toggle("cohorts", facet.value)}
              count={facet.count}
            >
              {facet.label}
            </FilterChip>
          ))}
        </FilterRow>
      ) : null}

      {/* Count + sort */}
      <div className="mt-8 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 border-b border-mist pb-2">
        <div className="flex items-baseline gap-3">
          <h2 className="eyebrow">Directory</h2>
          <p aria-live="polite" className="font-mono text-xs text-faint">
            {countLabel}
          </p>
          {hasActiveFilters ? (
            <button
              type="button"
              onClick={clearAll}
              className="text-xs text-buoy-ink underline underline-offset-2 hover:no-underline"
            >
              Clear
            </button>
          ) : null}
        </div>
        <div className="flex items-baseline gap-2">
          <label htmlFor={sortId} className="eyebrow">
            Sort
          </label>
          <select
            id={sortId}
            value={state.sort}
            onChange={(event) => setSort(event.target.value as SortKey)}
            className="rounded-sm border border-mist bg-paper px-2 py-1 text-xs text-river focus-visible:border-buoy"
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Results */}
      {results.length > 0 ? (
        <ul className="divide-y divide-mist">
          {results.map((org) => (
            <OrgRow key={org.org_id} org={org} />
          ))}
        </ul>
      ) : (
        <div className="border-b border-mist py-14 text-center">
          <p className="display text-lg text-river">No organizations match this view</p>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted">
            {state.q.trim()
              ? `Nothing matches “${state.q.trim()}”`
              : "No organizations match the selected filters"}
            . Try a different term or loosen the filters.
          </p>
          <button
            type="button"
            onClick={clearAll}
            className="mt-5 inline-flex items-center justify-center rounded-sm border border-buoy px-3 py-2 text-sm font-medium text-buoy-ink transition-colors hover:bg-buoy hover:text-paper"
          >
            Clear search
          </button>
        </div>
      )}
    </section>
  );
}

function FilterRow({
  label,
  children,
  className
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3 ${className ?? ""}`}>
      <span className="eyebrow shrink-0 sm:w-28">{label}</span>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </div>
  );
}

function SearchGlyph({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  );
}

function CloseGlyph({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}
