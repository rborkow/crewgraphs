import type { OrgProfilePayload } from "@crewgraphs/contracts";
import { ProvenancedValue } from "@/components/provenanced-value";
import { filingStatusLabel, formatShare, isFiledStatus } from "@/lib/profile-format";
import type {
  Composition,
  CompositionCell,
  CompositionRow,
  CompositionTable
} from "@/lib/read-model";

type CoverageStatus = OrgProfilePayload["coverage"][number]["status"];

/**
 * Revenue & spending detail: the composition lines behind the trend charts, as
 * two years-across-columns tables — "where the money comes from" and "where the
 * money goes". Every cell is a ProvenancedValue (opens its SourceDrawer); a
 * hole is a line the filing's form doesn't carry, rendered as an em dash, while
 * a published $0 stays a real zero. Lines are shown as reported — the tables
 * never claim the lines sum to the total, because the 990 and 990-EZ nest them
 * differently (see the per-table footnotes).
 */
export function FinancialComposition({
  composition,
  coverage,
  slug
}: {
  composition: Composition;
  coverage: OrgProfilePayload["coverage"];
  slug: string;
}) {
  const { years, revenue, expenses } = composition;
  const hasRevenue = revenue.groups.length > 0;
  const hasExpenses = expenses.groups.length > 0;
  if (years.length === 0 || (!hasRevenue && !hasExpenses)) return null;

  const statusByYear = new Map(coverage.map((entry) => [entry.tax_year, entry.status]));

  return (
    <section className="border-b border-mist py-8">
      <h2 className="eyebrow">Revenue &amp; spending detail</h2>

      <div className="mt-5 flex flex-col gap-10">
        {hasRevenue ? (
          <CompositionFigure
            title="Where the money comes from"
            table={revenue}
            years={years}
            statusByYear={statusByYear}
            slug={slug}
            footnote="Lines are shown as reported on the filing and can overlap: on the full Form 990, membership dues are included within contributions & grants, and net fundraising-event income within other revenue; on the 990-EZ each is its own line. Lines the club never itemized are omitted."
          />
        ) : null}
        {hasExpenses ? (
          <CompositionFigure
            title="Where the money goes"
            table={expenses}
            years={years}
            statusByYear={statusByYear}
            slug={slug}
            footnote="The program / management / fundraising split is reported only on the full Form 990. Line items are shown as reported and overlap the split. Lines the club never itemized are omitted."
          />
        ) : null}
      </div>
    </section>
  );
}

function CompositionFigure({
  title,
  table,
  years,
  statusByYear,
  slug,
  footnote
}: {
  title: string;
  table: CompositionTable;
  years: number[];
  statusByYear: Map<number, CoverageStatus>;
  slug: string;
  footnote: string;
}) {
  return (
    <div>
      <h3 className="mb-3 text-sm font-semibold text-river">{title}</h3>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[36rem] border-collapse text-sm">
          <thead>
            <tr className="border-b border-mist text-left">
              <th scope="col" className="py-2 pr-4 font-medium text-faint">
                <span className="sr-only">Line</span>
              </th>
              {years.map((year) => {
                const status = statusByYear.get(year);
                return (
                  <th key={year} scope="col" className="py-2 pl-4 text-right align-bottom">
                    <div className="font-medium text-faint">FY{year}</div>
                    {status && isFiledStatus(status) ? (
                      <div className="text-[11px] font-normal text-faint">
                        {filingStatusLabel(status)}
                      </div>
                    ) : null}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {table.total ? (
              <LineRow row={table.total} years={years} slug={slug} emphasized />
            ) : null}
            {table.groups.map((group, index) => (
              <GroupRows
                key={group.label ?? index}
                label={group.label}
                rows={group.rows}
                years={years}
                slug={slug}
              />
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 max-w-prose text-xs leading-relaxed text-faint">{footnote}</p>
    </div>
  );
}

function GroupRows({
  label,
  rows,
  years,
  slug
}: {
  label: string | null;
  rows: CompositionRow[];
  years: number[];
  slug: string;
}) {
  return (
    <>
      {label ? (
        <tr>
          <th
            scope="colgroup"
            colSpan={years.length + 1}
            className="eyebrow pb-1 pt-4 text-left text-faint"
          >
            {label}
          </th>
        </tr>
      ) : null}
      {rows.map((row) => (
        <LineRow key={row.key} row={row} years={years} slug={slug} />
      ))}
    </>
  );
}

function LineRow({
  row,
  years,
  slug,
  emphasized = false
}: {
  row: CompositionRow;
  years: number[];
  slug: string;
  emphasized?: boolean;
}) {
  return (
    <tr className="border-b border-mist last:border-0">
      <th
        scope="row"
        className={`py-2 pr-4 text-left font-normal ${emphasized ? "font-medium text-river" : "text-muted"}`}
      >
        {row.label}
      </th>
      {years.map((year) => (
        <td key={year} className="py-2 pl-4 text-right align-top">
          <LineCell cell={row.cells[year]} label={`${row.label} — FY${year}`} slug={slug} />
        </td>
      ))}
    </tr>
  );
}

function LineCell({
  cell,
  label,
  slug
}: {
  cell: CompositionCell | undefined;
  label: string;
  slug: string;
}) {
  // A hole means the line is not on that year's form (e.g. the functional
  // split on a 990-EZ year) — distinct from a published $0, which renders.
  if (!cell) {
    return (
      <span className="text-faint">
        —<span className="sr-only"> not reported on this year&apos;s form</span>
      </span>
    );
  }
  return (
    <div className="flex flex-col items-end gap-0.5">
      <ProvenancedValue refData={cell.ref} label={label} orgSlug={slug} />
      {cell.share !== null ? (
        <span className="text-[11px] leading-none text-faint">{formatShare(cell.share)}</span>
      ) : null}
    </div>
  );
}
