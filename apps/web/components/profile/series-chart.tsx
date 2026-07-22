"use client";

import { useState } from "react";
import { ChartWithTable, type AnnualSeries, type ChartKind } from "@crewgraphs/charts";
import type { SourceRef } from "@crewgraphs/contracts";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { SourceDrawer } from "@/components/source-drawer";
// Import the pure helper from the db-free read-model module — importing it from
// the profile-data seam would drag the server-only `pg` client into this client
// component's browser bundle.
import { provenanceKey } from "@/lib/read-model";

export interface SeriesChartProps {
  series: AnnualSeries;
  ariaSummary: string;
  kind: ChartKind;
  /**
   * SourceRefs keyed by `${series_key}::${tax_year}` (see profile-data). The
   * chart kit is decoupled from provenance — a point carries no SourceRef — so
   * on activation we look the ref up here and open the drawer ourselves.
   */
  provenance: Record<string, SourceRef>;
  orgSlug: string;
}

/**
 * Client wrapper that gives every chart point a SourceDrawer. The kit fires
 * `onPointActivate(point, series)` with no SourceRef; we resolve it from the
 * provenance map by (series.key, point.tax_year) and open a controlled drawer.
 */
export function SeriesChart({ series, ariaSummary, kind, provenance, orgSlug }: SeriesChartProps) {
  const [activeRef, setActiveRef] = useState<SourceRef | null>(null);

  return (
    <>
      <ChartWithTable
        kind={kind}
        series={series}
        ariaSummary={ariaSummary}
        onPointActivate={(point, activated) => {
          const ref = provenance[provenanceKey(activated.key, point.tax_year)];
          if (ref) setActiveRef(ref);
        }}
      />
      <Sheet open={activeRef !== null} onOpenChange={(open) => (open ? null : setActiveRef(null))}>
        <SheetContent aria-describedby={undefined}>
          {activeRef ? (
            <SourceDrawer refData={activeRef} label={series.label} orgSlug={orgSlug} />
          ) : null}
        </SheetContent>
      </Sheet>
    </>
  );
}
