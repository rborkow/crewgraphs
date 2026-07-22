import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export type ChipTone = "buoy" | "gold";

export interface FilterChipProps {
  active: boolean;
  onToggle: () => void;
  children: ReactNode;
  /** Buoy for the quiet type/coverage toggles; gold for peer-cohort chips. */
  tone?: ChipTone;
  /** Small trailing count, e.g. facet size. */
  count?: number;
}

const BASE =
  "inline-flex items-center gap-1.5 whitespace-nowrap rounded-sm border px-2.5 py-1 text-xs font-medium leading-none transition-colors";

const TONE_CLASSES: Record<ChipTone, { on: string; off: string; count: string }> = {
  buoy: {
    off: "border-mist bg-transparent text-muted hover:border-buoy hover:text-buoy-ink",
    on: "border-buoy bg-buoy text-paper hover:bg-buoy-ink",
    count: "text-faint"
  },
  gold: {
    off: "border-gold/60 bg-transparent text-gold hover:border-gold hover:bg-gold/10",
    on: "border-gold bg-gold text-river",
    count: "text-river/70"
  }
};

/**
 * A quiet, keyboard-native toggle. It is a real `<button>` carrying
 * `aria-pressed`, so multi-select filter state is exposed to assistive tech and
 * driven entirely from the keyboard.
 */
export function FilterChip({ active, onToggle, children, tone = "buoy", count }: FilterChipProps) {
  const palette = TONE_CLASSES[tone];
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onToggle}
      className={cn(BASE, active ? palette.on : palette.off)}
    >
      <span>{children}</span>
      {typeof count === "number" ? (
        <span className={cn("font-mono text-[0.65rem]", active ? "" : palette.count)}>{count}</span>
      ) : null}
    </button>
  );
}
