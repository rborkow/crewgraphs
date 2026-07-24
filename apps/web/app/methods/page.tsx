import type { Metadata } from "next";
import Link from "next/link";
import { getPublishMeta } from "@/lib/directory";
import { getMetricCatalog, getSourceRegistry } from "@/lib/methods-data";
import {
  CONCEPT_GROUP_LABELS,
  CONCEPT_MAP,
  CONCEPT_MAP_VERSION,
  type ConceptGroup,
  type ConceptMapEntry
} from "@/lib/concept-map";
import { eligibilityConditions, type MetricCatalogEntry } from "@/lib/methods-model";

// Reads the published metric catalog and source registry on every request,
// like the rest of the site: the prose is static, the catalogs are data.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Methods — CrewGraphs",
  description:
    "How CrewGraphs turns public IRS filings into the figures on this site: sources and licenses, the concept map, missing-versus-zero rules, quality states, comparison alignment, and every metric definition."
};

const SECTIONS = [
  { id: "sources", label: "Sources & licenses" },
  { id: "concepts", label: "From filing to figure" },
  { id: "missing-vs-zero", label: "Missing vs. zero" },
  { id: "quality-states", label: "Quality states" },
  { id: "comparisons", label: "Comparing organizations" },
  { id: "amendments", label: "Amended returns" },
  { id: "people", label: "People" },
  { id: "metrics", label: "Metric definitions" },
  { id: "corrections", label: "Corrections" }
] as const;

export default async function MethodsPage() {
  const [metricCatalog, sourceRegistry, publishMeta] = await Promise.all([
    getMetricCatalog(),
    getSourceRegistry(),
    getPublishMeta()
  ]);

  return (
    <main className="mx-auto w-full max-w-5xl px-5 sm:px-8">
      <header className="pb-4 pt-10">
        <p className="eyebrow">Methods</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-river">
          How these figures are made
        </h1>
        <p className="mt-4 max-w-2xl text-sm text-muted">
          CrewGraphs is a reference for the identity and nonprofit finances of US rowing
          organizations, built entirely from public IRS filings. Every figure on the site carries
          its provenance: click any number to see the exact filing, form line, and parser version
          it came from. This page documents the rules that connect a filing to a figure — and the
          places where the honest answer is &ldquo;the form doesn&rsquo;t say.&rdquo;
        </p>
        {publishMeta ? (
          <p className="mt-3 text-sm text-faint">{publishMeta.data_through_label}.</p>
        ) : null}
      </header>

      <nav aria-label="On this page" className="border-y border-mist py-3">
        <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
          {SECTIONS.map((section) => (
            <li key={section.id}>
              <a href={`#${section.id}`} className="text-muted no-underline hover:underline">
                {section.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <section id="sources" className="scroll-mt-6 py-8">
        <h2 className="eyebrow">Sources &amp; licenses</h2>
        <p className="mt-3 max-w-2xl text-sm text-muted">
          Everything published here originates in five public sources. Filings are fetched as the
          IRS-published XML, stored immutably with checksums, and parsed by our own extractor —
          no source&rsquo;s numbers are republished wholesale, and no figure is displayed without a
          link back to where it came from.
        </p>

        <dl className="mt-5 space-y-4">
          {sourceRegistry.map((source) => (
            <div key={source.source_key} className="rounded-md border border-mist bg-surface p-4">
              <dt className="font-medium text-river">{source.display_name}</dt>
              <dd className="mt-1 max-w-2xl text-sm text-muted">{source.description}</dd>
              <dd className="mt-1 max-w-2xl text-sm text-faint">{source.attribution}</dd>
            </div>
          ))}
          {sourceRegistry.length === 0 ? (
            <div className="rounded-md border border-mist bg-surface p-4 text-sm text-muted">
              The published source registry will appear here once a snapshot is live.
            </div>
          ) : null}
        </dl>

        <p className="mt-4 max-w-2xl text-sm text-muted">
          Per-filing XML is retrieved from the GivingTuesday 990 Data Lake, which is made available
          under the{" "}
          <a
            href="https://opendatacommons.org/licenses/odbl/1-0/"
            target="_blank"
            rel="noreferrer"
            className="underline"
          >
            Open Database License (ODbL) v1.0
          </a>
          ; databases derived from it, including this one, remain subject to its share-alike terms.
          ProPublica&rsquo;s Nonprofit Explorer is used to cross-check our extraction — six anchor
          values per filing must match exactly — but ProPublica values are never published as
          CrewGraphs facts. Our concept map was seeded with reference to the Nonprofit Open Data
          Collective&rsquo;s master concordance, which we acknowledge with thanks.
        </p>
      </section>

      <section id="concepts" className="scroll-mt-6 border-t border-mist py-8">
        <h2 className="eyebrow">From filing to figure</h2>
        <p className="mt-3 max-w-2xl text-sm text-muted">
          CrewGraphs extracts a fixed catalog of 24 financial concepts from each Form 990 or
          990-EZ — nothing more. Each concept maps to specific elements of the IRS e-file XML
          schema, listed below exactly as the extractor reads them (concept map{" "}
          <code className="font-mono text-xs">{CONCEPT_MAP_VERSION}</code>). The provenance drawer
          on any figure shows the same element as the value&rsquo;s source path.
        </p>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          When the map or extractor changes, filings are re-parsed under a new version and the
          results are published as new value rows — published history is corrected forward, never
          edited in place.
        </p>

        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[44rem] border-collapse text-sm">
            <thead>
              <tr className="border-b border-mist text-left">
                <th scope="col" className="py-2 pr-4 font-medium text-faint">
                  Concept
                </th>
                <th scope="col" className="py-2 pr-4 font-medium text-faint">
                  Form 990
                </th>
                <th scope="col" className="py-2 font-medium text-faint">
                  Form 990-EZ
                </th>
              </tr>
            </thead>
            <tbody>
              {(Object.keys(CONCEPT_GROUP_LABELS) as ConceptGroup[]).map((group) => (
                <ConceptGroupRows key={group} group={group} />
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 max-w-2xl text-xs text-faint">
          Where two elements are listed, filings across schema years name the same line
          differently and the extractor accepts either. A dash means the form has no such line —
          see the missing-vs-zero rule below.
        </p>
      </section>

      <section id="missing-vs-zero" className="scroll-mt-6 border-t border-mist py-8">
        <h2 className="eyebrow">Missing vs. zero</h2>
        <p className="mt-3 max-w-2xl text-sm text-muted">
          The strictest rule on the site: an absence of data is never shown as a value of zero.
          The two mean different things, and IRS forms make the distinction constantly.
        </p>
        <ul className="mt-4 max-w-2xl list-disc space-y-2 pl-5 text-sm text-muted">
          <li>
            <span className="font-medium text-river">Not on the form.</span> Form 990-EZ has no
            line for several concepts (management &amp; general expense, fundraising expense,
            professional fundraising fees, employee count). For EZ filers these render as
            &ldquo;unavailable — not on 990-EZ,&rdquo; never as $0.
          </li>
          <li>
            <span className="font-medium text-river">Not filed that year.</span> Gaps in a trend
            are left as gaps. Lines are never interpolated across a missing year, and the IRS
            e-file corpus itself has a documented thin patch in 2021&ndash;2022 that no processing
            on our side can fill.
          </li>
          <li>
            <span className="font-medium text-river">Form 990-N filers.</span> The e-Postcard
            confirms a small organization is active but reports no financial figures at all.
            990-N-only organizations appear with their filing years and an explanation — presence,
            not financials. Roughly a fifth of known rowing organizations live here permanently,
            by design of the form.
          </li>
          <li>
            <span className="font-medium text-river">Timing.</span> Every figure is dated to the
            fiscal year it represents. Public filings lag their fiscal year end by 6&ndash;18
            months, so the newest complete year on a profile is usually one to two years behind
            today.
          </li>
        </ul>
      </section>

      <section id="quality-states" className="scroll-mt-6 border-t border-mist py-8">
        <h2 className="eyebrow">Quality states</h2>
        <p className="mt-3 max-w-2xl text-sm text-muted">
          Every published value carries one of five quality states, shown as a chip wherever the
          value appears:
        </p>
        <dl className="mt-4 max-w-2xl space-y-3 text-sm">
          <QualityState name="Verified">
            Read directly from an IRS filing at the source path shown in the provenance drawer.
          </QualityState>
          <QualityState name="Derived">
            Computed by CrewGraphs from verified inputs under a versioned metric definition (the
            catalog below). The drawer lists the definition and version.
          </QualityState>
          <QualityState name="Partial">
            The form reports the concept incompletely — for example, the 990-EZ cash line mixes
            cash with investments. Shown with the caveat, and never eligible for rankings.
          </QualityState>
          <QualityState name="Unavailable">
            The form has no line for this concept, or the year is unfiled. Distinct from zero,
            always labeled.
          </QualityState>
          <QualityState name="Under review">
            Something about the filing doesn&rsquo;t reconcile — most commonly a return whose own
            reported totals fail an accounting identity. The value is held out of comparisons and
            rankings until a person has reviewed it, rather than published as fact.
          </QualityState>
        </dl>
      </section>

      <section id="comparisons" className="scroll-mt-6 border-t border-mist py-8">
        <h2 className="eyebrow">Comparing organizations</h2>
        <p className="mt-3 max-w-2xl text-sm text-muted">
          Comparisons align on the IRS tax year (<code className="font-mono text-xs">TaxYr</code>)
          from each return&rsquo;s header, not the calendar year the fiscal year happens to end
          in — for a June-fiscal-year club, &ldquo;FY2023&rdquo; is the year that began in July
          2023. Each organization&rsquo;s fiscal year end month is surfaced alongside, and the
          compare page defaults to the newest tax year all selected organizations have filed.
        </p>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          A caution that matters in rowing: the racing name on the water and the legal entity that
          files with the IRS are different things in roughly two of every five organizations here —
          booster clubs, school programs, sibling foundations. Profiles state whose money is being
          shown and link related entities, and comparisons should be read the same way.
        </p>
      </section>

      <section id="amendments" className="scroll-mt-6 border-t border-mist py-8">
        <h2 className="eyebrow">Amended returns</h2>
        <p className="mt-3 max-w-2xl text-sm text-muted">
          When an organization files an amended return, the amendment becomes the authoritative
          source for that year and its figures carry an &ldquo;amended&rdquo; marker. The
          superseded original is retained — provenance links keep working — but it no longer feeds
          published figures.
        </p>
      </section>

      <section id="people" className="scroll-mt-6 border-t border-mist py-8">
        <h2 className="eyebrow">People</h2>
        <p className="mt-3 max-w-2xl text-sm text-muted">
          Officer and director listings come from each filing&rsquo;s compensation schedule (Form
          990 Part VII; the 990-EZ officer table). Most rowing nonprofit boards are volunteers, so
          profiles list compensated individuals with their reported role, hours, and compensation,
          and summarize uncompensated directors as a count — less noise, and no republishing of
          volunteers&rsquo; names. People appear for every filed year, exactly as reported.
        </p>
      </section>

      <section id="metrics" className="scroll-mt-6 border-t border-mist py-8">
        <h2 className="eyebrow">Metric definitions</h2>
        <p className="mt-3 max-w-2xl text-sm text-muted">
          Derived metrics are versioned definitions, published with the same provenance as raw
          concepts. There is deliberately no composite &ldquo;club score&rdquo;: each metric states
          what it measures, what a value needs to qualify, and what it cannot tell you.
        </p>

        {metricCatalog.length === 0 ? (
          <div className="mt-5 rounded-md border border-mist bg-surface p-4 text-sm text-muted">
            The published metric catalog will appear here once a snapshot is live.
          </div>
        ) : (
          <div className="mt-5 space-y-4">
            {metricCatalog.map((metric) => (
              <MetricCard key={metric.key} metric={metric} />
            ))}
          </div>
        )}
      </section>

      <section id="corrections" className="scroll-mt-6 border-t border-mist py-8">
        <h2 className="eyebrow">Corrections</h2>
        <p className="mt-3 max-w-2xl text-sm text-muted">
          If a figure looks wrong, it is either faithfully extracted from a filing that is itself
          wrong, or our extraction erred — both are worth hearing about. Every profile has a{" "}
          <Link href="/corrections/new" className="underline">
            report a correction
          </Link>{" "}
          entry point; corrections are reviewed by a person and resolved through the same audited
          process as every other identity decision on the site.
        </p>
      </section>
    </main>
  );
}

function ConceptGroupRows({ group }: { group: ConceptGroup }) {
  const entries = CONCEPT_MAP.filter((entry) => entry.group === group);
  return (
    <>
      <tr>
        <th colSpan={3} scope="colgroup" className="eyebrow pb-1 pt-5 text-left text-faint">
          {CONCEPT_GROUP_LABELS[group]}
        </th>
      </tr>
      {entries.map((entry) => (
        <ConceptRow key={entry.key} entry={entry} />
      ))}
    </>
  );
}

function ConceptRow({ entry }: { entry: ConceptMapEntry }) {
  return (
    <tr className="border-t border-mist align-top">
      <th scope="row" className="py-2 pr-4 text-left font-normal">
        <span className="font-medium text-river">{entry.label}</span>
        {entry.note ? <span className="mt-0.5 block text-xs text-faint">{entry.note}</span> : null}
      </th>
      <td className="py-2 pr-4">
        <ElementList elements={entry.form990} />
      </td>
      <td className="py-2">
        <ElementList elements={entry.form990ez} />
      </td>
    </tr>
  );
}

function ElementList({ elements }: { elements: string[] }) {
  if (elements.length === 0) {
    return <span className="text-faint">&mdash;</span>;
  }
  return (
    <span className="flex flex-col gap-0.5">
      {elements.map((element) => (
        <code key={element} className="break-all font-mono text-xs text-muted">
          {element}
        </code>
      ))}
    </span>
  );
}

function QualityState({ name, children }: { name: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="font-medium text-river">{name}</dt>
      <dd className="text-muted">{children}</dd>
    </div>
  );
}

function MetricCard({ metric }: { metric: MetricCatalogEntry }) {
  const conditions = eligibilityConditions(metric.eligibility_rule);
  return (
    <article
      id={`metric-${metric.key}`}
      className="scroll-mt-6 rounded-md border border-mist bg-surface p-5"
    >
      <h3 className="font-medium text-river">
        <Link href={`/methods/${metric.key}`} className="no-underline hover:underline">
          {metric.label}
        </Link>
      </h3>
      <p className="mt-0.5 font-mono text-xs text-faint">
        {metric.key} · v{metric.version} · {metric.unit}
      </p>
      <p className="mt-2 max-w-2xl text-sm text-muted">{metric.description}</p>
      {conditions.length > 0 ? (
        <p className="mt-2 max-w-2xl text-sm text-muted">
          <span className="font-medium text-river">Eligibility:</span> {conditions.join(" ")}
        </p>
      ) : null}
      {metric.limitation ? (
        <p className="mt-1 max-w-2xl text-sm text-faint">
          <span className="font-medium">Limitation:</span> {metric.limitation}
        </p>
      ) : null}
    </article>
  );
}
