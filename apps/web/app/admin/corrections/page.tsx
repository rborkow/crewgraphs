import type { Metadata } from "next";
import Link from "next/link";
import { AdminStatusChip } from "@/components/admin/status-chip";
import { requireAdminAccess } from "@/lib/admin-gate";
import { getAdminCorrections } from "@/lib/admin-data";
import { adminDate, detailsText } from "@/lib/admin-model";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Correction submissions — CrewGraphs",
  robots: { index: false, follow: false }
};

export default async function AdminCorrectionsPage() {
  await requireAdminAccess();
  const corrections = await getAdminCorrections();

  return (
    <main className="mx-auto w-full max-w-6xl px-5 pb-14 sm:px-8">
      <header className="border-b border-mist pb-6 pt-10">
        <Link href="/admin" className="text-sm underline">
          Admin
        </Link>
        <p className="eyebrow mt-5">Read-only queue</p>
        <h1 className="display mt-2 text-4xl text-river">Correction submissions</h1>
      </header>

      {corrections.length === 0 ? (
        <p className="py-10 text-sm text-muted">No correction submissions.</p>
      ) : (
        <div className="overflow-x-auto py-6">
          <table className="w-full min-w-[64rem] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-mist text-faint">
                <th className="py-2 pr-4 font-medium">Received</th>
                <th className="py-2 pr-4 font-medium">Organization</th>
                <th className="py-2 pr-4 font-medium">Message</th>
                <th className="py-2 pr-4 font-medium">Details</th>
                <th className="py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {corrections.map((correction) => {
                const created = adminDate(correction.created_at);
                return (
                  <tr key={correction.id} className="border-b border-mist align-top">
                    <td className="py-4 pr-4 text-xs text-muted">
                      <time dateTime={created.iso}>{created.label}</time>
                    </td>
                    <td className="py-4 pr-4">
                      <p className="font-medium text-river">
                        {correction.org_display_name ?? correction.org_slug ?? "Unresolved"}
                      </p>
                      {correction.organization_id ? (
                        <p className="mt-1 font-mono text-xs text-faint">
                          {correction.organization_id}
                        </p>
                      ) : null}
                    </td>
                    <td className="max-w-md whitespace-pre-wrap py-4 pr-4 text-river">
                      {correction.message}
                    </td>
                    <td className="max-w-sm py-4 pr-4">
                      <pre className="whitespace-pre-wrap font-mono text-xs text-muted">
                        {detailsText(correction.details)}
                      </pre>
                    </td>
                    <td className="py-4">
                      <AdminStatusChip status={correction.status} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
