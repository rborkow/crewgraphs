import type { ReactNode } from "react";
import type { SourceRef } from "@crewgraphs/contracts";
import { SheetBody, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { QualityChip, qualityStateLabel, type QualityState } from "@/components/quality-chip";
import { formatDate, formatExact } from "@/lib/format";

// Factual, non-hedging plain-language for each quality state.
const QUALITY_COPY: Record<QualityState, string> = {
  verified: "Taken directly from the organization's filing as submitted to the IRS.",
  derived: "Calculated by CrewGraphs from reported figures. The formula and version are listed under Method.",
  partial: "Only part of this figure is available from the filing; the reported total is incomplete.",
  unavailable: "This figure is not reported on the form this organization filed.",
  under_review: "Held out of rankings and comparisons while CrewGraphs reviews the underlying filing."
};

const FORM_TYPE_LABELS: Record<SourceRef["source"]["form_type"], string> = {
  "990": "Form 990",
  "990EZ": "Form 990-EZ",
  "990N": "Form 990-N (e-Postcard)"
};

export interface SourceDrawerProps {
  refData: SourceRef;
  /** Human metric label, e.g. "Total revenue". */
  label: string;
  /** Correction-link context; the route may 404 during the design phase. */
  orgSlug?: string;
  metricKey?: string;
}

function Field({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs text-faint">{term}</dt>
      <dd className="text-sm text-river">{children}</dd>
    </div>
  );
}

function Section({ eyebrow, children }: { eyebrow: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="eyebrow">{eyebrow}</h3>
      {children}
    </section>
  );
}

export function SourceDrawer({ refData, label, orgSlug, metricKey }: SourceDrawerProps) {
  const { value, unit, period, quality_state, source, retrieved_at, parser_version, metric } = refData;
  const correctionMetric = metricKey ?? metric?.key ?? "";

  const params = new URLSearchParams();
  if (orgSlug) params.set("org", orgSlug);
  if (correctionMetric) params.set("metric", correctionMetric);
  params.set("period", String(period.tax_year));
  const correctionHref = `/corrections/new?${params.toString()}`;

  return (
    <>
      <SheetHeader>
        <span className="eyebrow">Source &amp; provenance</span>
        <SheetTitle>{label}</SheetTitle>
        <div className="mt-2 flex items-baseline gap-3">
          <span className="font-mono text-2xl tracking-tight text-river">
            {value === null ? qualityStateLabel(quality_state) : formatExact(value, unit)}
          </span>
          {value !== null ? <span className="text-xs text-faint">{unit}</span> : null}
          <QualityChip state={quality_state} className="ml-auto" />
        </div>
      </SheetHeader>

      <SheetBody>
        {/* Represents vs Retrieved — deliberately separated: the period a number
            describes is not the moment it was fetched. */}
        <Section eyebrow="Represents">
          <p className="text-sm text-river">{period.label}</p>
          <dl className="grid grid-cols-2 gap-4">
            <Field term="Tax year">{period.tax_year}</Field>
            <Field term="Fiscal year end">{formatDate(period.fy_end)}</Field>
          </dl>
        </Section>

        <Section eyebrow="Retrieved">
          <dl>
            <Field term="Fetched by CrewGraphs">{formatDate(retrieved_at)}</Field>
          </dl>
          <p className="text-xs text-faint">
            When the filing was collected — not when the reporting period ended. Public filings lag their
            fiscal year by 6–18 months.
          </p>
        </Section>

        <Section eyebrow="Source">
          <dl className="flex flex-col gap-3">
            <Field term="Form">{FORM_TYPE_LABELS[source.form_type]}</Field>
            <Field term="Filing">
              <span className="font-mono text-xs">{source.filing_id}</span>
            </Field>
            <Field term="Location in filing">
              <span className="break-all font-mono text-xs">{source.source_path}</span>
            </Field>
            {source.raw_url ? (
              <Field term="Raw filing">
                <a href={source.raw_url} target="_blank" rel="noreferrer" className="underline">
                  View source document
                </a>
              </Field>
            ) : null}
          </dl>
          {source.is_amended ? (
            <p className="text-xs text-muted">
              This value comes from an <strong className="font-semibold">amended</strong> return, which
              supersedes the original filing.
            </p>
          ) : null}
        </Section>

        <Section eyebrow="Method">
          <dl className="flex flex-col gap-3">
            <Field term="Concept map / parser">
              <span className="font-mono text-xs">{parser_version}</span>
            </Field>
            {metric ? (
              <Field term="Metric definition">
                <span className="font-mono text-xs">
                  {metric.key} · v{metric.version}
                </span>
              </Field>
            ) : null}
          </dl>
        </Section>

        <Section eyebrow="Data quality">
          <p className="text-sm text-river">{QUALITY_COPY[quality_state]}</p>
        </Section>
      </SheetBody>

      <SheetFooter>
        <a
          href={correctionHref}
          className="inline-flex items-center justify-center rounded-sm border border-buoy px-3 py-2 text-sm font-medium text-buoy-ink transition-colors hover:bg-buoy hover:text-paper"
        >
          Report a correction
        </a>
      </SheetFooter>
    </>
  );
}
