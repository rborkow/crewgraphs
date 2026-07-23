import Link from "next/link";
import type { SeasonBlock } from "@/lib/regatta-read-model";
import { RESULT_SOURCE_LABELS } from "@/lib/regatta-read-model";
import { ResultValue } from "@/components/result-value";
import { formatDate } from "@/lib/format";

/**
 * Regatta activity from timing providers. Renders season-grouped regattas with
 * this org's entries; every figure is a ResultValue (full ResultRef required),
 * regattas link out to the provider's official record, and the footer carries
 * the attribution + takedown line the PII policy requires. With no published
 * results (no curated club links yet, or none ingested), the section keeps the
 * reserved-slot posture the placeholder established.
 */
export function RegattaActivity({ seasons }: { seasons: SeasonBlock[] }) {
  if (seasons.length === 0) {
    return (
      <section className="border-b border-mist py-8">
        <div className="rounded-md border border-mist p-5">
          <p className="eyebrow text-faint">Regatta activity</p>
          <p className="mt-2 max-w-2xl text-sm text-muted">
            No linked race results for this organization yet. Results flow in as timing-provider
            records are matched to club identities — matching is curated, never guessed.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="border-b border-mist py-8">
      <h2 className="eyebrow">Regatta activity</h2>

      <div className="mt-4 flex flex-col gap-8">
        {seasons.map((season) => (
          <div key={season.season}>
            <p className="text-sm text-muted">{season.season} season</p>

            <div className="mt-3 flex flex-col gap-6">
              {season.regattas.map((regatta) => (
                <div key={regatta.regattaKey} className="rounded-md border border-mist p-4">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <p className="text-base text-river">{regatta.name}</p>
                    <p className="text-xs text-faint">
                      {[
                        regatta.date ? formatDate(regatta.date) : null,
                        regatta.venue
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                  </div>

                  <div className="mt-3 overflow-x-auto">
                    <table className="w-full min-w-[36rem] border-collapse text-sm">
                      <thead>
                        <tr className="border-b border-mist text-left">
                          <th className="py-2 pr-4 font-medium text-faint">Event</th>
                          <th className="py-2 pr-4 text-right font-medium text-faint">Place</th>
                          <th className="py-2 pr-4 text-right font-medium text-faint">Time</th>
                          <th className="py-2 pr-4 text-right font-medium text-faint">Adjusted</th>
                          <th className="py-2 text-right font-medium text-faint">Margin</th>
                        </tr>
                      </thead>
                      <tbody>
                        {regatta.entries.map((entry) => {
                          const entryLabel = [entry.eventName, entry.round, entry.crewLabel]
                            .filter(Boolean)
                            .join(" · ");
                          return (
                            <tr
                              key={`${entry.eventKey}:${entry.crewLabel ?? ""}`}
                              className="border-b border-mist last:border-0"
                            >
                              <td className="py-2 pr-4">
                                <span className="text-river">{entryLabel}</span>
                                {entry.status !== "finished" && entry.metrics.finish_time == null ? (
                                  <span className="ml-2 text-xs uppercase text-faint">
                                    {entry.status}
                                  </span>
                                ) : null}
                                {entry.crew.length > 0 ? (
                                  <span className="block text-xs text-faint">
                                    {entry.crew
                                      .map((member) => `${member.role} ${member.name}`)
                                      .join(" · ")}
                                  </span>
                                ) : null}
                              </td>
                              <td className="py-2 pr-4 text-right">
                                {entry.metrics.place ? (
                                  <ResultValue
                                    refData={entry.metrics.place}
                                    label={`${entryLabel} — place`}
                                  />
                                ) : (
                                  <span className="text-muted">—</span>
                                )}
                              </td>
                              <td className="py-2 pr-4 text-right">
                                {entry.metrics.finish_time ? (
                                  <ResultValue
                                    refData={entry.metrics.finish_time}
                                    label={`${entryLabel} — finish time`}
                                  />
                                ) : (
                                  <span className="text-muted">—</span>
                                )}
                              </td>
                              <td className="py-2 pr-4 text-right">
                                {entry.metrics.adjusted_time ? (
                                  <ResultValue
                                    refData={entry.metrics.adjusted_time}
                                    label={`${entryLabel} — adjusted time`}
                                  />
                                ) : (
                                  <span className="text-muted">—</span>
                                )}
                              </td>
                              <td className="py-2 text-right">
                                {entry.metrics.margin ? (
                                  <ResultValue
                                    refData={entry.metrics.margin}
                                    label={`${entryLabel} — margin`}
                                  />
                                ) : (
                                  <span className="text-muted">—</span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>

                  {regatta.providerUrl ? (
                    <a
                      href={regatta.providerUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-3 inline-block text-xs text-muted hover:underline"
                    >
                      Official record at{" "}
                      {RESULT_SOURCE_LABELS[regatta.sourceKey] ?? regatta.sourceKey} ↗
                    </a>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <p className="mt-4 max-w-2xl text-xs text-faint">
        Results are ingested from timing providers&rsquo; published records and link back to the
        official source. Athlete names appear only in race-result context, as published; anyone can
        request removal of their name — see{" "}
        <Link href="/methods" className="hover:underline">
          how CrewGraphs sources data
        </Link>
        .
      </p>
    </section>
  );
}
