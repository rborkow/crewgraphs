import type { OrgProfilePayload } from "@crewgraphs/contracts";

type CoverageState = OrgProfilePayload["header"]["coverage_state"];

const EXPLAINERS: Record<CoverageState, { title: string; body: string } | null> = {
  "990n_only": {
    title: "This organization files Form 990-N (the e-Postcard)",
    body:
      "Form 990-N is the IRS e-Postcard for small tax-exempt organizations. It confirms the organization is active and files each year, but it reports no revenue, expense, or balance-sheet figures — so there are no financial trends to chart here. The filing years on record are shown above."
  },
  none: {
    title: "No IRS filings are on record yet",
    body:
      "CrewGraphs has not matched any public IRS filing to this organization. When a filing is found and reviewed, its financial figures will appear here. Until then there is nothing to chart — an absence of data, not a value of zero."
  },
  // 990 / 990ez filers always have at least one charted concept; the explainer
  // is a graceful fallback if a filer somehow has no chartable series.
  "990": {
    title: "Not enough filed years to chart a trend yet",
    body:
      "This organization has a filing on record but not yet enough comparable years to draw a trend. Its figures are shown in the snapshot above, and more years will appear as filings are processed."
  },
  "990ez": {
    title: "Not enough filed years to chart a trend yet",
    body:
      "This organization files Form 990-EZ, and there are not yet enough comparable years to draw a trend. Its figures are shown in the snapshot above, and more years will appear as filings are processed."
  }
};

/**
 * A designed, plain-language panel that stands in for empty charts — a
 * 990-N-only filer, or an org without a chartable series. Never an empty hole.
 */
export function CoverageExplainer({ coverageState }: { coverageState: CoverageState }) {
  const copy = EXPLAINERS[coverageState] ?? EXPLAINERS.none!;
  return (
    <div className="rounded-md border border-mist bg-surface p-5">
      <p className="eyebrow text-faint">Financial detail</p>
      <p className="mt-2 font-medium text-river">{copy.title}</p>
      <p className="mt-2 max-w-2xl text-sm text-muted">{copy.body}</p>
    </div>
  );
}
