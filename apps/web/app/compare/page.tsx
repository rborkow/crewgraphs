import type { Metadata } from "next";
import { Suspense } from "react";
import { getDirectory } from "@/lib/directory";
import { getCompareSeries } from "@/lib/compare-data";
import {
  buildComparisonRows,
  deriveComparisonYear,
  parseOrgSlugs,
  parseTaxYear,
  resolveComparisonSelection
} from "@/lib/compare-model";
import { OrganizationPicker } from "@/components/compare/organization-picker";
import { ComparisonTable } from "@/components/compare/comparison-table";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Compare organizations — CrewGraphs",
  description: "Compare rowing organizations on the same IRS TaxYr, with every value sourced."
};

interface ComparePageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

function firstParam(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function ComparePage({ searchParams }: ComparePageProps) {
  const params = await searchParams;
  const parsedSlugs = parseOrgSlugs(firstParam(params.orgs));
  const explicitYear = parseTaxYear(firstParam(params.fy));
  const directory = await getDirectory();
  const selection = resolveComparisonSelection(directory.entries, parsedSlugs.slugs);
  const yearState = deriveComparisonYear(selection.organizations, explicitYear);

  const seriesRows =
    selection.organizations.length >= 2 && yearState.selectedYear !== null
      ? await getCompareSeries(
          directory.snapshot_id,
          selection.organizations.map((organization) => organization.org_id),
          yearState.selectedYear
        )
      : [];
  const comparisonRows = buildComparisonRows(seriesRows);

  const csvParams = new URLSearchParams();
  if (selection.organizations.length > 0) {
    csvParams.set("orgs", selection.organizations.map((organization) => organization.slug).join(","));
  }
  if (yearState.selectedYear !== null) csvParams.set("fy", String(yearState.selectedYear));

  return (
    <main className="mx-auto w-full max-w-5xl px-5 sm:px-8">
      <header className="border-b border-mist pb-8 pt-10 sm:pb-10 sm:pt-14">
        <p className="eyebrow">Side-by-side filings</p>
        <h1 className="display mt-3 max-w-3xl text-4xl text-river sm:text-5xl">
          Compare organizations on a shared IRS tax year.
        </h1>
        <p className="mt-4 max-w-2xl text-base text-muted sm:text-lg">
          Align two to four published organizations by TaxYr, while keeping each fiscal calendar
          and every source visible.
        </p>
      </header>

      <Suspense fallback={null}>
        <OrganizationPicker
          entries={directory.entries}
          candidateCommonYears={yearState.candidateCommonYears}
          selectedYear={yearState.selectedYear}
        />
      </Suspense>

      {selection.unknownSlugs.length > 0 || selection.overflowSlugs.length > 0 ? (
        <div role="status" className="border-b border-mist py-4 text-sm text-muted">
          {selection.unknownSlugs.length > 0 ? (
            <p>
              Unknown organizations were left out: {selection.unknownSlugs.join(", ")}.
            </p>
          ) : null}
          {selection.overflowSlugs.length > 0 ? (
            <p>Only the first four organizations can be compared; later entries were left out.</p>
          ) : null}
        </div>
      ) : null}

      {selection.organizations.length < 2 ? (
        <section className="border-b border-mist py-14 text-center">
          <p className="display text-xl text-river">Choose at least two organizations</p>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted">
            Search the published directory above and add organizations to begin a sourced
            comparison.
          </p>
        </section>
      ) : yearState.selectedYear === null ? (
        <section className="border-b border-mist py-14 text-center">
          <p className="display text-xl text-river">No filed tax years are available</p>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted">
            These organizations do not yet have a filed IRS TaxYr to compare.
          </p>
        </section>
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-mist py-4">
            <p className="text-sm text-muted">
              {yearState.usedNoCommonYearFallback
                ? `No common filed TaxYr was found. Showing the newest filed year, FY${yearState.selectedYear}, with unavailable cells where needed.`
                : `Showing IRS TaxYr FY${yearState.selectedYear}.`}
            </p>
            <a
              href={`/api/compare?${csvParams.toString()}`}
              className="text-sm font-medium underline decoration-buoy/60 hover:decoration-buoy"
            >
              Download CSV
            </a>
          </div>
          <ComparisonTable
            organizations={selection.organizations}
            rows={comparisonRows}
            taxYear={yearState.selectedYear}
          />
        </>
      )}
    </main>
  );
}
