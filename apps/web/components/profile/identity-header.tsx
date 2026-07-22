import type { OrgProfilePayload } from "@crewgraphs/contracts";
import { BladeIdenticon } from "@/components/blade-identicon";
import { CoverageBadge } from "@/components/coverage-badge";
import { orgTypeLabel } from "@/lib/format";
import { programLabel } from "@/lib/profile-format";

function hostname(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

function locationLine(city: string | null, state: string | null): string | null {
  if (city && state) return `${city}, ${state}`;
  return city ?? state ?? null;
}

export function IdentityHeader({
  header,
  orgId
}: {
  header: OrgProfilePayload["header"];
  orgId: string;
}) {
  const legalDiffers = header.legal_name !== null && header.legal_name !== header.display_name;
  const location = locationLine(header.city, header.state);
  const meta = [location, orgTypeLabel(header.org_type)].filter(Boolean).join(" · ");

  return (
    <header className="border-b border-mist py-8 sm:py-10">
      <div className="flex items-start gap-4 sm:gap-5">
        <BladeIdenticon orgId={orgId} size={48} className="mt-1 shrink-0" />

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <h1 className="display text-3xl text-river sm:text-4xl">{header.display_name}</h1>
            <CoverageBadge state={header.coverage_state} />
          </div>

          {legalDiffers ? (
            <p className="mt-1 text-sm text-muted">Legal name: {header.legal_name}</p>
          ) : null}

          {meta ? <p className="mt-2 text-sm text-muted">{meta}</p> : null}

          {/* Whose money is shown is a trust feature, surfaced under the names —
              not a footnote. */}
          {header.filer_note ? (
            <p className="mt-3 border-l-2 border-buoy pl-3 text-sm text-river">{header.filer_note}</p>
          ) : null}

          {header.program_mix.length > 0 || header.website ? (
            <div className="mt-4 flex flex-wrap items-center gap-2">
              {header.program_mix.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center whitespace-nowrap rounded-sm border border-mist px-1.5 py-0.5 text-[0.68rem] font-medium leading-none text-muted"
                >
                  {programLabel(tag)}
                </span>
              ))}
              {header.website ? (
                <a
                  href={header.website}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm hover:underline"
                >
                  {hostname(header.website)}
                </a>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </header>
  );
}
