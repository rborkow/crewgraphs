"use client";

import type { SourceRef } from "@crewgraphs/contracts";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { SourceDrawer } from "@/components/source-drawer";
import { QualityChip, qualityStateLabel } from "@/components/quality-chip";
import { defaultFormatForUnit, formatValue, type ValueFormat } from "@/lib/format";
import { cn } from "@/lib/utils";

export interface ProvenancedValueProps {
  /** The provenance atom. Required — a value with no source is unrepresentable. */
  refData: SourceRef;
  format?: ValueFormat;
  /** Human metric label for the drawer title, e.g. "Total revenue". */
  label?: string;
  /** Correction-link context (route may 404 during the design phase). */
  orgSlug?: string;
  metricKey?: string;
  className?: string;
}

/**
 * The single sanctioned way to render a metric. Renders the formatted value in
 * tabular mono with a dotted buoy underline; the whole affordance is a dialog
 * trigger that opens the SourceDrawer. Non-verified states carry an inline
 * QualityChip; a null value renders its state label — never 0, never blank.
 */
export function ProvenancedValue({
  refData,
  format,
  label,
  orgSlug,
  metricKey,
  className
}: ProvenancedValueProps) {
  const { value, unit, quality_state } = refData;
  const fmt = format ?? defaultFormatForUnit(unit);
  const isNull = value === null;
  const display = isNull ? qualityStateLabel(quality_state) : formatValue(value, fmt);
  const showChip = !isNull && quality_state !== "verified";
  const drawerLabel = label ?? refData.metric?.key ?? "Reported figure";

  return (
    <Sheet>
      <SheetTrigger
        className={cn(
          "group inline-flex items-baseline gap-1.5 rounded-sm text-left",
          className
        )}
        aria-haspopup="dialog"
      >
        <span
          className={cn(
            "font-mono underline decoration-dotted underline-offset-4 decoration-buoy/70 group-hover:decoration-buoy",
            isNull && "text-muted"
          )}
        >
          {display}
        </span>
        {showChip ? <QualityChip state={quality_state} /> : null}
        <span className="sr-only"> — view source and provenance</span>
      </SheetTrigger>
      <SheetContent aria-describedby={undefined}>
        <SourceDrawer refData={refData} label={drawerLabel} orgSlug={orgSlug} metricKey={metricKey} />
      </SheetContent>
    </Sheet>
  );
}
