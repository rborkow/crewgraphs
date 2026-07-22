import type { DirectoryEntry } from "@crewgraphs/contracts";
import { cn } from "@/lib/utils";

export type CoverageState = DirectoryEntry["coverage_state"];

const COVERAGE_LABELS: Record<CoverageState, string> = {
  "990": "Form 990",
  "990ez": "Form 990-EZ",
  "990n_only": "990-N filer",
  none: "No filings"
};

export interface CoverageBadgeProps {
  state: CoverageState;
  className?: string;
}

export function CoverageBadge({ state, className }: CoverageBadgeProps) {
  return (
    <span
      data-coverage-state={state}
      className={cn(
        "inline-flex items-center whitespace-nowrap rounded-sm border border-mist bg-surface px-1.5 py-0.5 text-[0.68rem] font-medium leading-none text-muted",
        className
      )}
    >
      {COVERAGE_LABELS[state]}
    </span>
  );
}
