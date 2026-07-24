import type { Metadata } from "next";
import { getDirectory } from "@/lib/directory";
import { CorrectionForm } from "@/components/corrections/correction-form";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Report a correction — CrewGraphs",
  description: "Flag a source or extraction issue for human review."
};

interface CorrectionPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

function firstParam(value: string | string[] | undefined): string | undefined {
  const first = Array.isArray(value) ? value[0] : value;
  const trimmed = first?.trim();
  return trimmed || undefined;
}

export default async function NewCorrectionPage({ searchParams }: CorrectionPageProps) {
  const params = await searchParams;
  const orgSlug = firstParam(params.org);
  let orgDisplayName: string | undefined;

  if (orgSlug) {
    try {
      const directory = await getDirectory();
      orgDisplayName = directory.entries.find((entry) => entry.slug === orgSlug)?.display_name;
    } catch {
      // Reporting remains available if the published directory is temporarily unavailable.
    }
  }

  return (
    <main className="mx-auto w-full max-w-3xl px-5 pb-14 sm:px-8">
      <header className="border-b border-mist pb-8 pt-10 sm:pb-10 sm:pt-14">
        <p className="eyebrow">Corrections</p>
        <h1 className="display mt-3 text-4xl text-river sm:text-5xl">Report a correction.</h1>
        <p className="mt-4 max-w-2xl text-base text-muted">
          A figure can be faithfully extracted from a source that is itself wrong, or our
          extraction can be wrong. Both reports are welcome. Tell us what you found and a person
          will review the source.
        </p>
      </header>

      <section className="py-8 sm:py-10">
        <CorrectionForm orgSlug={orgSlug} orgDisplayName={orgDisplayName} />
      </section>
    </main>
  );
}
