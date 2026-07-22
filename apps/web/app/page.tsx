import { directory } from "@/lib/directory";
import { orgTypeLabel } from "@/lib/format";
import { BladeIdenticon } from "@/components/blade-identicon";
import { CoverageBadge } from "@/components/coverage-badge";

function humanizeCohort(slug: string): string {
  const words = slug.replace(/[-_]/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export default function HomePage() {
  const entries = [...directory.entries].sort((a, b) => a.display_name.localeCompare(b.display_name));

  return (
    <main className="mx-auto w-full max-w-5xl px-5 sm:px-8">
      {/* Hero */}
      <section className="border-b border-mist py-14 sm:py-20">
        <p className="eyebrow">US rowing organizations</p>
        <h1 className="display mt-3 max-w-3xl text-4xl text-river sm:text-5xl">
          Identity and financial context for rowing clubs, with the source behind every number.
        </h1>
        <p className="mt-5 max-w-2xl text-base text-muted sm:text-lg">
          CrewGraphs brings a rowing organization&rsquo;s canonical identity together with its public IRS
          financial record — one trusted reference, every displayed figure traceable to its filing.
        </p>
      </section>

      {/* Directory preview */}
      <section className="py-10 sm:py-14">
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="eyebrow">Directory</h2>
          <span className="font-mono text-xs text-faint">{entries.length} organizations</span>
        </div>

        <ul className="mt-4 divide-y divide-mist border-y border-mist">
          {entries.map((org) => (
            <li key={org.org_id} className="flex items-start gap-3 py-3 sm:items-center sm:gap-4">
              <BladeIdenticon orgId={org.org_id} size={26} className="mt-0.5 shrink-0 sm:mt-0" />
              <div className="flex min-w-0 flex-1 flex-col gap-x-4 gap-y-1 sm:flex-row sm:items-center">
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-river">{org.display_name}</p>
                  <p className="text-xs text-muted">
                    {org.city}, {org.state} · {orgTypeLabel(org.org_type)}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                  {org.peer_cohorts.map((cohort) => (
                    <span
                      key={cohort}
                      className="inline-flex items-center whitespace-nowrap rounded-sm border border-gold/60 px-1.5 py-0.5 text-[0.68rem] font-medium leading-none text-gold"
                      title={`Peer cohort: ${humanizeCohort(cohort)}`}
                    >
                      {humanizeCohort(cohort)}
                    </span>
                  ))}
                  <CoverageBadge state={org.coverage_state} />
                </div>
              </div>
            </li>
          ))}
        </ul>

        <p className="mt-4 text-xs text-faint">
          Preview of the fixture cohort. Full alias-aware search and organization profiles follow.
        </p>
      </section>
    </main>
  );
}
