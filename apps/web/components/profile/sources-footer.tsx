import type { OrgProfilePayload } from "@crewgraphs/contracts";
import { directory } from "@/lib/directory";
import { coverageSourceSummary } from "@/lib/profile-format";

/**
 * Sources & corrections. States which forms and years underlie the profile
 * (from coverage), the data-through note, the represented-vs-retrieved
 * distinction in one plain sentence, and a correction entry point.
 */
export function SourcesFooter({
  coverage,
  slug
}: {
  coverage: OrgProfilePayload["coverage"];
  slug: string;
}) {
  const summary = coverageSourceSummary(coverage);

  return (
    <section className="py-8">
      <h2 className="eyebrow">Sources &amp; corrections</h2>

      <p className="mt-3 max-w-2xl text-sm text-muted">
        This profile is built from public IRS filings — {summary}. {directory.data_through_label}.
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
