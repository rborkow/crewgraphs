import type { OrgProfilePayload } from "@crewgraphs/contracts";
import { ProvenancedValue } from "@/components/provenanced-value";
import { snapshotFactFormat } from "@/lib/profile-format";

/**
 * The snapshot: the payload's provenanced facts as a clean heat-sheet fact row
 * — label eyebrow over a ProvenancedValue — not stat-tile cards. Every value
 * opens the SourceDrawer, and a null value renders its quality word, never 0.
 */
export function SnapshotFacts({
  snapshot,
  slug
}: {
  snapshot: OrgProfilePayload["snapshot"];
  slug: string;
}) {
  return (
    <section className="border-b border-mist py-8">
      <h2 className="eyebrow">Snapshot</h2>
      <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-6 sm:grid-cols-3 lg:grid-cols-4">
        {snapshot.map((fact) => (
          <div key={fact.key} className="flex min-w-0 flex-col gap-1.5">
            <dt className="eyebrow text-faint">{fact.label}</dt>
            <dd className="text-lg leading-none">
              <ProvenancedValue
                refData={fact.ref}
                label={fact.label}
                orgSlug={slug}
                metricKey={fact.ref.metric?.key}
                format={snapshotFactFormat(fact.ref)}
              />
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
