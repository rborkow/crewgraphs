import type { OrgProfilePayload } from "@crewgraphs/contracts";
import { filingStatusLabel } from "@/lib/profile-format";
import { cn } from "@/lib/utils";

/**
 * The filing-coverage timeline: one chip per tax year showing what is on record.
 * Missing years are shown explicitly (dashed, "No filing") — the deterministic
 * missing-vs-zero story from the spec — so a gap is never silently a zero.
 */
export function CoverageTimeline({ coverage }: { coverage: OrgProfilePayload["coverage"] }) {
  const years = [...coverage].sort((a, b) => a.tax_year - b.tax_year);

  return (
    <div>
      <h3 className="eyebrow text-faint">Filing coverage</h3>
      <ol className="mt-2 flex flex-wrap gap-2">
        {years.map((c) => {
          const missing = c.status === "missing" || c.status === "not_yet_expected";
          const amended = c.status === "amended";
          return (
            <li
              key={c.tax_year}
              data-status={c.status}
              className={cn(
                "flex flex-col items-center rounded-sm border px-2.5 py-1 text-center",
                missing ? "border-mist border-dashed" : "border-mist bg-surface"
              )}
            >
              <span className="font-mono text-xs text-river">FY{c.tax_year}</span>
              <span
                className={cn(
                  "mt-0.5 text-[0.62rem] leading-none",
                  missing ? "text-faint" : amended ? "text-gold" : "text-muted"
                )}
              >
                {filingStatusLabel(c.status)}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
