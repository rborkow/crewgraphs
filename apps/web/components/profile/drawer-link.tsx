"use client";

import type { ReactNode } from "react";
import type { SourceRef } from "@crewgraphs/contracts";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { SourceDrawer } from "@/components/source-drawer";
import { cn } from "@/lib/utils";

export interface DrawerLinkProps {
  refData: SourceRef;
  /** Drawer title, e.g. "People from filings, FY2024". */
  label: string;
  orgSlug?: string;
  metricKey?: string;
  className?: string;
  /** The visible trigger content — arbitrary text, not a formatted value. */
  children: ReactNode;
}

/**
 * A text affordance that opens the SourceDrawer for a SourceRef. Unlike
 * `ProvenancedValue` (which renders a formatted metric), this wraps arbitrary
 * copy — used where a whole section (a year's people, a filing) has one source
 * behind it rather than a single number.
 */
export function DrawerLink({ refData, label, orgSlug, metricKey, className, children }: DrawerLinkProps) {
  return (
    <Sheet>
      <SheetTrigger
        className={cn(
          "rounded-sm text-left underline decoration-dotted decoration-buoy/70 underline-offset-4 hover:decoration-buoy",
          className
        )}
        aria-haspopup="dialog"
      >
        {children}
        <span className="sr-only"> — view source and provenance</span>
      </SheetTrigger>
      <SheetContent aria-describedby={undefined}>
        <SourceDrawer refData={refData} label={label} orgSlug={orgSlug} metricKey={metricKey} />
      </SheetContent>
    </Sheet>
  );
}
