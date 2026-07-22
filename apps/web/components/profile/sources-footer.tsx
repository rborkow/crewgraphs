import type { OrgProfilePayload } from "@crewgraphs/contracts";
import { coverageSourceSummary } from "@/lib/profile-format";

/**
 * Sources & corrections. States which forms and years underlie the profile
 * (from coverage), the data-through note, the represented-vs-retrieved
 * distinction in one plain sentence, and a correction entry point.
 *
 * The data-through label is passed in from the page (which reads it from the
 * published snapshot) so this component stays presentational.
 */
export function SourcesFooter({
  coverage,
  slug,
  dataThroughLabel
}: {
  coverage: OrgProfilePayload["coverage"];
  slug: string;
  dataThroughLabel: string;
}) {
  const summary = coverageSourceSummary(coverage);

  return (
    <section className="py-8">
      <h2 className="eyebrow">Sources &amp; corrections</h2>

      <p className="mt-3 max-w-2xl text-sm text-muted">
        This profile is built from public IRS filings — {summary}. {dataThroughLabel}.
      </p>
      <p className="mt-2 max-w-2xl text-sm text-muted">
        Every figure is dated to the fiscal year it represents, not the day CrewGraphs retrieved the
        filing; public filings lag their fiscal year by 6&ndash;18 months.
      </p>

      <p className="mt-4 text-sm">
        <a href={`/corrections/new?org=${slug}`} className="hover:underline">
          Report a correction
        </a>
      </p>
    </section>
  );
}
