import Link from "next/link";
import type { DirectoryEntry } from "@crewgraphs/contracts";
import { orgTypeLabel } from "@/lib/format";
import { humanizeCohort } from "@/lib/directory-search";
import { BladeIdenticon } from "@/components/blade-identicon";
import { CoverageBadge } from "@/components/coverage-badge";

export interface OrgRowProps {
  org: DirectoryEntry;
}

/**
 * One directory row, rendered as a single full-width link to the org profile
 * (which may 404 until the profile route lands). The identicon + wrapped name +
 * meta + chip layout is preserved exactly; the name is never truncated, so long
 * names wrap rather than clip.
 */
export function OrgRow({ org }: OrgRowProps) {
  const location = [org.city, org.state].filter(Boolean).join(", ");
  const meta = location ? `${location} · ${orgTypeLabel(org.org_type)}` : orgTypeLabel(org.org_type);

  return (
    <li>
      <Link
        href={`/org/${org.slug}`}
        className="group -mx-2 flex items-start gap-3 rounded-sm px-2 py-3 no-underline transition-colors hover:bg-surface sm:items-center sm:gap-4"
      >
        <BladeIdenticon orgId={org.org_id} size={26} className="mt-0.5 shrink-0 sm:mt-0" />
        <div className="flex min-w-0 flex-1 flex-col gap-x-4 gap-y-1 sm:flex-row sm:items-center">
          <div className="min-w-0 flex-1">
            <p className="font-medium text-river underline-offset-2 group-hover:text-buoy-ink group-hover:underline">
              {org.display_name}
            </p>
            <p className="text-xs text-muted">{meta}</p>
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
      </Link>
    </li>
  );
}
