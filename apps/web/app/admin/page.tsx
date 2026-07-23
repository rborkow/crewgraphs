import type { Metadata } from "next";
import Link from "next/link";
import { requireAdminAccess } from "@/lib/admin-gate";
import { getAdminCounts } from "@/lib/admin-data";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Admin — CrewGraphs",
  robots: { index: false, follow: false }
};

export default async function AdminPage() {
  await requireAdminAccess();
  const counts = await getAdminCounts();

  return (
    <main className="mx-auto w-full max-w-5xl px-5 pb-14 sm:px-8">
      <header className="border-b border-mist pb-8 pt-10">
        <p className="eyebrow">Read-only admin</p>
        <h1 className="display mt-3 text-4xl text-river">Review queues</h1>
        <p className="mt-3 max-w-2xl text-sm text-muted">
          Queue visibility only. Status changes remain in the audited curation CLI.
        </p>
      </header>

      <div className="grid gap-4 py-8 sm:grid-cols-2">
        <Link
          href="/admin/corrections"
          className="rounded-md border border-mist bg-surface p-5 no-underline"
        >
          <p className="eyebrow">Corrections</p>
          <p className="display mt-3 text-4xl text-river">{counts.pendingCorrections}</p>
          <p className="mt-2 text-sm text-muted">Pending submissions</p>
        </Link>
        <Link
          href="/admin/review"
          className="rounded-md border border-mist bg-surface p-5 no-underline"
        >
          <p className="eyebrow">Curation</p>
          <p className="display mt-3 text-4xl text-river">{counts.openReviewTasks}</p>
          <p className="mt-2 text-sm text-muted">Open review tasks</p>
        </Link>
      </div>
    </main>
  );
}
