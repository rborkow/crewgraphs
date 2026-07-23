"use client";

import { useId, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { DirectoryEntry } from "@crewgraphs/contracts";
import { entryMatchesQuery, normalize } from "@/lib/directory-search";
import { parseOrgSlugs } from "@/lib/compare-model";

export function OrganizationPicker({
  entries,
  candidateCommonYears,
  selectedYear
}: {
  entries: DirectoryEntry[];
  candidateCommonYears: number[];
  selectedYear: number | null;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [query, setQuery] = useState("");
  const searchId = useId();
  const yearId = useId();

  const entryBySlug = useMemo(() => new Map(entries.map((entry) => [entry.slug, entry])), [entries]);
  const selected = parseOrgSlugs(searchParams.get("orgs")).slugs
    .map((slug) => entryBySlug.get(slug))
    .filter((entry): entry is DirectoryEntry => Boolean(entry))
    .slice(0, 4);
  const selectedSlugs = selected.map((entry) => entry.slug);

  const results = useMemo(() => {
    const normalized = normalize(query);
    if (!normalized) return [];
    return entries
      .filter(
        (entry) =>
          !selectedSlugs.includes(entry.slug) && entryMatchesQuery(entry, normalized)
      )
      .slice(0, 6);
  }, [entries, query, selectedSlugs]);

  function replaceUrl(slugs: string[], year?: number) {
    const params = new URLSearchParams(searchParams.toString());
    if (slugs.length > 0) params.set("orgs", slugs.join(","));
    else params.delete("orgs");
    if (year === undefined) params.delete("fy");
    else params.set("fy", String(year));
    const next = params.toString();
    router.replace(next ? `${pathname}?${next}` : pathname, { scroll: false });
  }

  function addOrganization(slug: string) {
    if (selectedSlugs.length >= 4 || selectedSlugs.includes(slug)) return;
    replaceUrl([...selectedSlugs, slug]);
    setQuery("");
  }

  function removeOrganization(slug: string) {
    replaceUrl(selectedSlugs.filter((selectedSlug) => selectedSlug !== slug));
  }

  const selectedYearIsCommon =
    selectedYear !== null && candidateCommonYears.includes(selectedYear);

  return (
    <section aria-labelledby="compare-picker-heading" className="border-b border-mist py-7">
      <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
        <div className="min-w-0 flex-1">
          <h2 id="compare-picker-heading" className="eyebrow">
            Organizations
          </h2>
          <div className="mt-3 flex flex-wrap gap-2" aria-live="polite">
            {selected.length > 0 ? (
              selected.map((organization) => (
                <span
                  key={organization.org_id}
                  className="inline-flex items-center gap-2 rounded-sm border border-mist bg-surface px-2.5 py-1.5 text-sm text-river"
                >
                  <span className="max-w-56 truncate">{organization.display_name}</span>
                  <button
                    type="button"
                    onClick={() => removeOrganization(organization.slug)}
                    aria-label={`Remove ${organization.display_name}`}
                    className="flex size-5 items-center justify-center rounded-sm text-faint transition-colors hover:text-river"
                  >
                    <span aria-hidden="true">×</span>
                  </button>
                </span>
              ))
            ) : (
              <p className="text-sm text-faint">No organizations selected yet.</p>
            )}
          </div>

          <div className="relative mt-4 max-w-xl">
            <label htmlFor={searchId} className="sr-only">
              Search published organizations to compare
            </label>
            <input
              id={searchId}
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              disabled={selected.length >= 4}
              autoComplete="off"
              spellCheck={false}
              placeholder={
                selected.length >= 4 ? "Four-organization limit reached" : "Add an organization…"
              }
              className="w-full rounded-sm border border-mist bg-paper px-3 py-2.5 text-sm text-river placeholder:text-faint disabled:cursor-not-allowed disabled:bg-surface focus-visible:border-buoy"
            />
            {query ? (
              <div className="absolute z-10 mt-1 w-full border border-mist bg-paper shadow-[0_6px_18px_rgba(14,27,44,0.12)]">
                {results.length > 0 ? (
                  <ul>
                    {results.map((organization) => (
                      <li key={organization.org_id} className="border-b border-mist last:border-0">
                        <button
                          type="button"
                          onClick={() => addOrganization(organization.slug)}
                          className="flex w-full items-baseline justify-between gap-4 px-3 py-2.5 text-left hover:bg-surface"
                        >
                          <span className="text-sm font-medium text-river">
                            {organization.display_name}
                          </span>
                          <span className="shrink-0 text-xs text-faint">
                            {[organization.city, organization.state].filter(Boolean).join(", ")}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="px-3 py-3 text-sm text-faint">No published organizations match.</p>
                )}
              </div>
            ) : null}
          </div>
          <p className="mt-2 text-xs text-faint">Select two to four organizations.</p>
        </div>

        <div className="shrink-0">
          <label htmlFor={yearId} className="eyebrow block">
            IRS TaxYr
          </label>
          <select
            id={yearId}
            value={selectedYearIsCommon ? String(selectedYear) : ""}
            disabled={candidateCommonYears.length === 0}
            onChange={(event) => {
              if (event.target.value) replaceUrl(selectedSlugs, Number(event.target.value));
            }}
            className="mt-3 min-w-44 rounded-sm border border-mist bg-paper px-3 py-2 text-sm text-river disabled:cursor-not-allowed disabled:bg-surface disabled:text-faint focus-visible:border-buoy"
          >
            {!selectedYearIsCommon ? (
              <option value="" disabled>
                {candidateCommonYears.length === 0
                  ? "No common TaxYr"
                  : selectedYear === null
                    ? "Choose a TaxYr"
                    : `FY${selectedYear} from URL`}
              </option>
            ) : null}
            {candidateCommonYears.map((year) => (
              <option key={year} value={year}>
                FY{year}
              </option>
            ))}
          </select>
        </div>
      </div>
    </section>
  );
}
