import type { OrgProfilePayload } from "@crewgraphs/contracts";
import { getTrends } from "@/lib/profile-data";
import { SeriesChart } from "@/components/profile/series-chart";
import { CoverageTimeline } from "@/components/profile/coverage-timeline";
import { CoverageExplainer } from "@/components/profile/coverage-explainer";

/**
 * Financial trends: one Chart | Table figure per charted concept (revenue,
 * expenses), each wired so a point opens its SourceDrawer. When there is no
 * chartable series (a 990-N-only filer), the coverage explainer stands in for
 * empty charts. The filing-coverage timeline always shows which years are on
 * record, so missing years are legible even without a chart.
 */
export function FinancialTrends({
  slug,
  coverage,
  coverageState
}: {
  slug: string;
  coverage: OrgProfilePayload["coverage"];
  coverageState: OrgProfilePayload["header"]["coverage_state"];
}) {
  const { charts, provenance } = getTrends(slug);

  return (
    <section className="border-b border-mist py-8">
      <h2 className="eyebrow">Financial trends</h2>

      <div className="mt-5">
        <CoverageTimeline coverage={coverage} />
      </div>

      {charts.length > 0 ? (
        <div className="mt-8 flex flex-col gap-10">
          {charts.map(({ series, ariaSummary, kind }) => (
            <div key={series.key}>
              <h3 className="mb-3 text-sm font-semibold text-river">{series.label}</h3>
              <SeriesChart
                series={series}
                ariaSummary={ariaSummary}
                kind={kind}
                provenance={provenance}
                orgSlug={slug}
              />
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-6">
          <CoverageExplainer coverageState={coverageState} />
        </div>
      )}
    </section>
  );
}
