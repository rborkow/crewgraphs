import Link from "next/link";

/**
 * A designed, dignified placeholder for the future regatta-activity source — a
 * slot the product reserves, not a hole. Results ingestion is permission-gated
 * (RegattaCentral, Concept2, row2k), so this ships as honest "coming soon".
 */
export function RegattaPlaceholder() {
  return (
    <section className="border-b border-mist py-8">
      <div className="rounded-md border border-mist p-5">
        <p className="eyebrow text-faint">Regatta activity — coming soon</p>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          Race results are a future CrewGraphs source. When permission-cleared results data lands, an
          organization&rsquo;s regatta activity will appear here alongside its filings.
        </p>
        <Link href="/methods" className="mt-3 inline-block text-sm hover:underline">
          How CrewGraphs sources data
        </Link>
      </div>
    </section>
  );
}
