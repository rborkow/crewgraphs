import { Suspense } from "react";
import { getDirectory } from "@/lib/directory";
import { DirectoryExplorer } from "@/components/directory/directory-explorer";

// The roster is read live from the published snapshot on each request.
export const dynamic = "force-dynamic";

export default async function HomePage() {
  const directory = await getDirectory();

  return (
    <main className="mx-auto w-full max-w-5xl px-5 sm:px-8">
      {/* Hero — kept concise so search sits above the fold on a laptop. */}
      <section className="border-b border-mist pt-10 pb-8 sm:pt-14 sm:pb-10">
        <p className="eyebrow">US rowing organizations</p>
        <h1 className="display mt-3 max-w-3xl text-4xl text-river sm:text-5xl">
          Identity and financial context for rowing clubs, with the source behind every number.
        </h1>
        <p className="mt-4 max-w-2xl text-base text-muted sm:text-lg">
          CrewGraphs brings a rowing organization&rsquo;s canonical identity together with its public IRS
          financial record — one trusted reference, every displayed figure traceable to its filing.
        </p>
      </section>

      {/* Directory: search + filters + browsable roster. Suspense satisfies the
          useSearchParams boundary requirement while the hero stays static. */}
      <Suspense fallback={null}>
        <DirectoryExplorer entries={directory.entries} />
      </Suspense>
    </main>
  );
}
