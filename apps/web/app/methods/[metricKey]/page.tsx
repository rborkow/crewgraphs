import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getMetricCatalog } from "@/lib/methods-data";
import { eligibilityConditions } from "@/lib/methods-model";

// A stable page per metric definition, so a metric can be cited by URL from
// provenance drawers, compare cells, and off-site. Unknown keys 404.
export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ metricKey: string }>;
}

async function getMetric(metricKey: string) {
  const catalog = await getMetricCatalog();
  return catalog.find((metric) => metric.key === metricKey) ?? null;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { metricKey } = await params;
  const metric = await getMetric(metricKey);
  if (!metric) return { title: "Metric — CrewGraphs" };
  return {
    title: `${metric.label} — Methods — CrewGraphs`,
    description: metric.description
  };
}

export default async function MetricPage({ params }: PageProps) {
  const { metricKey } = await params;
  const metric = await getMetric(metricKey);
  if (!metric) notFound();

  const conditions = eligibilityConditions(metric.eligibility_rule);

  return (
    <main className="mx-auto w-full max-w-5xl px-5 sm:px-8">
      <header className="pb-2 pt-10">
        <p className="eyebrow">
          <Link href="/methods" className="text-muted no-underline hover:underline">
            Methods
          </Link>{" "}
          / Metric definition
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-river">{metric.label}</h1>
        <p className="mt-1 font-mono text-xs text-faint">
          {metric.key} · version {metric.version} · unit: {metric.unit}
        </p>
      </header>

      <section className="max-w-2xl py-6 text-sm">
        <p className="text-muted">{metric.description}</p>

        <h2 className="eyebrow mt-6">Eligibility</h2>
        {conditions.length > 0 ? (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-muted">
            {conditions.map((condition) => (
              <li key={condition}>{condition}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-muted">
            No additional conditions beyond a verified underlying filing.
          </p>
        )}
        <p className="mt-2 text-faint">
          Years that fail an eligibility condition are shown as unavailable rather than computed
          anyway; partial and under-review inputs never feed this metric.
        </p>

        {metric.limitation ? (
          <>
            <h2 className="eyebrow mt-6">Limitation</h2>
            <p className="mt-2 text-muted">{metric.limitation}</p>
          </>
        ) : null}

        <p className="mt-8">
          <Link href="/methods" className="underline">
            All methods &amp; definitions
          </Link>
        </p>
      </section>
    </main>
  );
}
