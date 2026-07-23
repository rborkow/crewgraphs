import Link from "next/link";
import type { DirectoryEntry } from "@crewgraphs/contracts";
import { ProvenancedValue } from "@/components/provenanced-value";
import { QualityChip } from "@/components/quality-chip";
import {
  comparisonCellFormat,
  fyeMonthLabel,
  organizationsHaveDifferentFyes,
  type ComparisonViewRow
} from "@/lib/compare-model";

export function ComparisonTable({
  organizations,
  rows,
  taxYear
}: {
  organizations: DirectoryEntry[];
  rows: ComparisonViewRow[];
  taxYear: number;
}) {
  const formByOrg = new Map<string, "990" | "990EZ" | "990N">();
  for (const row of rows) {
    for (const [organizationId, cell] of Object.entries(row.cells)) {
      if (cell) formByOrg.set(organizationId, cell.ref.source.form_type);
    }
  }
  const fyesDiffer = organizationsHaveDifferentFyes(organizations);

  return (
    <section className="py-8" aria-labelledby="comparison-heading">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-mist pb-3">
        <div>
          <h2 id="comparison-heading" className="eyebrow">
            Financial comparison
          </h2>
          <p className="mt-2 text-sm text-muted">
            Aligned on IRS TaxYr <span className="font-mono text-river">FY{taxYear}</span>.
          </p>
        </div>
      </div>

      {fyesDiffer ? (
        <p className="mt-3 max-w-3xl text-xs leading-relaxed text-faint">
          Fiscal year ends differ across these organizations. Columns share the IRS TaxYr shown
          above, while the FYE labels identify each organization&rsquo;s reporting calendar.
        </p>
      ) : null}

      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[50rem] border-collapse text-sm">
          <thead>
            <tr className="border-b border-mist text-left">
              <th scope="col" className="w-52 py-3 pr-5 font-medium text-faint">
                Measure
              </th>
              {organizations.map((organization) => (
                <th
                  key={organization.org_id}
                  scope="col"
                  className="min-w-44 px-4 py-3 text-right align-bottom"
                >
                  <Link
                    href={`/org/${organization.slug}`}
                    className="font-medium text-river underline decoration-mist hover:decoration-buoy"
                  >
                    {organization.display_name}
                  </Link>
                  <span className="mt-1 block font-mono text-[11px] font-normal text-faint">
                    {fyeMonthLabel(organization.fye_month)}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <ComparisonLine
                key={row.key}
                row={row}
                organizations={organizations}
                taxYear={taxYear}
                formByOrg={formByOrg}
                startsDerived={row.kind === "derived" && rows[index - 1]?.kind !== "derived"}
              />
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-4 max-w-3xl text-xs leading-relaxed text-faint">
        Percent rows are derived from the same filing year. Select any populated value to inspect
        its source, period, parser version, and exact filing path.
      </p>
    </section>
  );
}

function ComparisonLine({
  row,
  organizations,
  taxYear,
  formByOrg,
  startsDerived
}: {
  row: ComparisonViewRow;
  organizations: DirectoryEntry[];
  taxYear: number;
  formByOrg: Map<string, "990" | "990EZ" | "990N">;
  startsDerived: boolean;
}) {
  return (
    <>
      {startsDerived ? (
        <tr>
          <th
            scope="colgroup"
            colSpan={organizations.length + 1}
            className="eyebrow border-b border-mist pb-2 pt-7 text-left text-faint"
          >
            Derived percentages
          </th>
        </tr>
      ) : null}
      <tr className="border-b border-mist last:border-0">
        <th scope="row" className="py-3 pr-5 text-left font-normal text-muted">
          {row.label}
        </th>
        {organizations.map((organization) => {
          const cell = row.cells[organization.org_id];
          return (
            <td key={organization.org_id} className="px-4 py-3 text-right align-top">
              {cell ? (
                <div className="flex flex-col items-end gap-1">
                  <ProvenancedValue
                    refData={cell.ref}
                    format={comparisonCellFormat(row, cell.ref)}
                    label={`${row.label} — ${organization.display_name}, FY${taxYear}`}
                    orgSlug={organization.slug}
                    metricKey={row.key}
                    alwaysShowQuality
                    className="justify-end"
                  />
                  {cell.qualityState === "unavailable" &&
                  cell.ref.source.form_type === "990EZ" ? (
                    <span className="text-[11px] text-faint">Not on 990-EZ</span>
                  ) : null}
                  {cell.isAmended ? (
                    <span className="text-[11px] text-faint">Amended return</span>
                  ) : null}
                </div>
              ) : (
                <UnavailableCell
                  filed={organization.filing_years.includes(taxYear)}
                  formType={formByOrg.get(organization.org_id)}
                />
              )}
            </td>
          );
        })}
      </tr>
    </>
  );
}

function UnavailableCell({
  filed,
  formType
}: {
  filed: boolean;
  formType: "990" | "990EZ" | "990N" | undefined;
}) {
  const reason = !filed
    ? "No filing for this TaxYr"
    : formType === "990EZ"
      ? "Not on 990-EZ"
      : "Not reported";
  return (
    <div className="flex flex-col items-end gap-1 text-faint">
      <span className="font-mono">Unavailable</span>
      <QualityChip state="unavailable" />
      <span className="text-[11px]">{reason}</span>
    </div>
  );
}
