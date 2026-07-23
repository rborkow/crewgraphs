"use client";

import type { ResultRef } from "@crewgraphs/contracts";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { QualityChip } from "@/components/quality-chip";
import { formatResultValue, RESULT_SOURCE_LABELS } from "@/lib/regatta-read-model";
import { cn } from "@/lib/utils";

/**
 * The results twin of ProvenancedValue: props require a full ResultRef, so an
 * unprovenanced race figure is unrepresentable. The drawer shows the timing
 * provider, the regatta/event source keys, retrieval time, parser version,
 * and the outbound provider page for the official record.
 */
export function ResultValue({
  refData,
  label,
  className
}: {
  refData: ResultRef;
  label: string;
  className?: string;
}) {
  const display = formatResultValue(refData);
  const providerLabel = RESULT_SOURCE_LABELS[refData.source.source_key] ?? refData.source.source_key;

  return (
    <Sheet>
      <SheetTrigger
        className={cn("group inline-flex items-baseline gap-1.5 rounded-sm text-left", className)}
        aria-haspopup="dialog"
      >
        <span className="font-mono underline decoration-dotted underline-offset-4 decoration-buoy/70 group-hover:decoration-buoy">
          {display}
        </span>
        {refData.quality_state !== "verified" ? <QualityChip state={refData.quality_state} /> : null}
        <span className="sr-only"> — view timing source</span>
      </SheetTrigger>
      <SheetContent aria-describedby={undefined}>
        <div className="flex h-full flex-col gap-4 p-5">
          <p className="eyebrow">Timing source</p>
          <p className="text-base text-river">{label}</p>

          <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-2 text-sm">
            <dt className="text-faint">Value</dt>
            <dd className="font-mono text-river">{display}</dd>
            <dt className="text-faint">Provider</dt>
            <dd className="text-river">{providerLabel}</dd>
            <dt className="text-faint">Season</dt>
            <dd className="text-river">{refData.season}</dd>
            <dt className="text-faint">Regatta key</dt>
            <dd className="font-mono text-xs text-muted">
              {refData.source.source_key}:{refData.source.regatta_external_key}
            </dd>
            <dt className="text-faint">Event key</dt>
            <dd className="font-mono text-xs text-muted">{refData.source.event_external_key}</dd>
            <dt className="text-faint">Retrieved</dt>
            <dd className="text-muted">{refData.retrieved_at}</dd>
            <dt className="text-faint">Parser</dt>
            <dd className="font-mono text-xs text-muted">{refData.parser_version}</dd>
          </dl>

          {refData.source.provider_url ? (
            <a
              href={refData.source.provider_url}
              target="_blank"
              rel="noreferrer"
              className="text-sm text-river hover:underline"
            >
              Official results at {providerLabel} ↗
            </a>
          ) : null}

          <p className="mt-auto text-xs text-faint">
            Times and placements are ingested verbatim from the timing provider&rsquo;s published
            record; CrewGraphs archives the raw payload and links back rather than restating it.
          </p>
        </div>
      </SheetContent>
    </Sheet>
  );
}
