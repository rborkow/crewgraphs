import type { SourceRef } from "@crewgraphs/contracts";
import { cn } from "@/lib/utils";

export type QualityState = SourceRef["quality_state"];

interface QualityMeta {
  glyph: string;
  label: string;
}

// Shape + label first — never colour alone. Muted ink for every state; only
// under_review carries the varnish-gold accent.
const QUALITY_META: Record<QualityState, QualityMeta> = {
  verified: { glyph: "✓", label: "Verified" },
  derived: { glyph: "ƒ", label: "Derived" },
  partial: { glyph: "◐", label: "Partial" },
  unavailable: { glyph: "—", label: "Unavailable" },
  under_review: { glyph: "⟳", label: "Under review" }
};

export interface QualityChipProps {
  state: QualityState;
  className?: string;
}

export function QualityChip({ state, className }: QualityChipProps) {
  const meta = QUALITY_META[state];
  const isReview = state === "under_review";

  return (
    <span
      data-quality-state={state}
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-sm border px-1.5 py-0.5 align-middle text-[0.68rem] font-medium leading-none",
        isReview ? "border-gold/60 text-gold" : "border-mist text-muted",
        className
      )}
    >
      <span aria-hidden="true" className="text-[0.8em] leading-none">
        {meta.glyph}
      </span>
      {meta.label}
    </span>
  );
}

/** The bare state label — used where value is null and the state must show as text. */
export function qualityStateLabel(state: QualityState): string {
  return QUALITY_META[state].label;
}
