import type { OrgProfilePayload } from "@crewgraphs/contracts";
import { ProvenancedValue } from "@/components/provenanced-value";
import { DrawerLink } from "@/components/profile/drawer-link";

/** Display labels for the Form 990 Part VII position checkboxes. */
const ROLE_LABELS: Record<string, string> = {
  individual_trustee_or_director: "Trustee/Director",
  officer: "Officer",
  key_employee: "Key employee",
  highest_compensated_employee: "Highest compensated",
  former_officer_director_trustee: "Former"
};

/**
 * People from filings. Per the spike display rule, only compensated individuals
 * are listed; the many $0 volunteer directors are collapsed into one aggregate
 * line. The compensated table shows name, title, average hours, and compensation
 * (each opening its own SourceDrawer); the aggregate line and the whole year are
 * sourced to the filing via the year's ref.
 *
 * Renders nothing when there are no people — the caller omits the section, but
 * this guard keeps the component safe to render directly.
 */
export function People({
  people,
  slug
}: {
  people: OrgProfilePayload["people"];
  slug: string;
}) {
  if (people.length === 0) return null;
  const years = [...people].sort((a, b) => b.tax_year - a.tax_year);

  return (
    <section className="border-b border-mist py-8">
      <h2 className="eyebrow">People from filings</h2>

      <div className="mt-4 flex flex-col gap-8">
        {years.map((year) => (
          <div key={year.tax_year}>
            <p className="text-sm text-muted">Reported on the FY{year.tax_year} filing</p>

            {year.compensated.length > 0 ? (
              <div className="mt-3 overflow-x-auto">
                <table className="w-full min-w-[32rem] border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-mist text-left">
                      <th className="py-2 pr-4 font-medium text-faint">Name</th>
                      <th className="py-2 pr-4 font-medium text-faint">Title</th>
                      <th className="py-2 pr-4 text-right font-medium text-faint">Avg h/wk</th>
                      <th className="py-2 text-right font-medium text-faint">Compensation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {year.compensated.map((person) => (
                      <tr key={person.name} className="border-b border-mist last:border-0">
                        <td className="py-2 pr-4 text-river">{person.name}</td>
                        <td className="py-2 pr-4 text-muted">
                          {person.title ?? "—"}
                          {person.role_flags.length > 0 ? (
                            <span className="block text-xs text-faint">
                              {person.role_flags
                                .map((flag) => ROLE_LABELS[flag] ?? flag)
                                .join(" · ")}
                            </span>
                          ) : null}
                        </td>
                        <td className="py-2 pr-4 text-right font-mono text-river">
                          {person.avg_hours_week ?? "—"}
                        </td>
                        <td className="py-2 text-right">
                          <ProvenancedValue
                            refData={person.ref}
                            label={`${person.name} — compensation`}
                            orgSlug={slug}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}

            <p className="mt-3 text-sm text-river">
              <DrawerLink
                refData={year.ref}
                label={`People from filings, FY${year.tax_year}`}
                orgSlug={slug}
              >
                {year.volunteer_count} volunteer board{" "}
                {year.volunteer_count === 1 ? "member" : "members"}, $0 compensation
              </DrawerLink>
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
