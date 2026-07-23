import type { Metadata } from "next";
import Link from "next/link";
import { AdminStatusChip } from "@/components/admin/status-chip";
import { requireAdminAccess } from "@/lib/admin-gate";
import {
  getAdminReviewTasks,
  getNewestAdminAuditEvents
} from "@/lib/admin-data";
import { adminDate, detailsText } from "@/lib/admin-model";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Review tasks — CrewGraphs",
  robots: { index: false, follow: false }
};

export default async function AdminReviewPage() {
  await requireAdminAccess();
  const [tasks, auditEvents] = await Promise.all([
    getAdminReviewTasks(),
    getNewestAdminAuditEvents()
  ]);

  return (
    <main className="mx-auto w-full max-w-6xl px-5 pb-14 sm:px-8">
      <header className="border-b border-mist pb-6 pt-10">
        <Link href="/admin" className="text-sm underline">
          Admin
        </Link>
        <p className="eyebrow mt-5">Read-only queue</p>
        <h1 className="display mt-2 text-4xl text-river">Review tasks</h1>
      </header>

      <section className="py-8">
        <h2 className="eyebrow">Tasks, open first</h2>
        {tasks.length === 0 ? (
          <p className="mt-4 text-sm text-muted">No review tasks.</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[60rem] border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-mist text-faint">
                  <th className="py-2 pr-4 font-medium">Created</th>
                  <th className="py-2 pr-4 font-medium">Task</th>
                  <th className="py-2 pr-4 font-medium">Entity</th>
                  <th className="py-2 pr-4 font-medium">Details</th>
                  <th className="py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => {
                  const created = adminDate(task.created_at);
                  return (
                    <tr key={task.id} className="border-b border-mist align-top">
                      <td className="py-4 pr-4 text-xs text-muted">
                        <time dateTime={created.iso}>{created.label}</time>
                      </td>
                      <td className="py-4 pr-4">
                        <p className="font-medium text-river">{task.task_type}</p>
                        {task.assigned_to ? (
                          <p className="mt-1 text-xs text-muted">Assigned to {task.assigned_to}</p>
                        ) : null}
                      </td>
                      <td className="py-4 pr-4">
                        <p className="text-river">{task.entity_type}</p>
                        <p className="mt-1 font-mono text-xs text-faint">{task.entity_id}</p>
                      </td>
                      <td className="max-w-md py-4 pr-4">
                        <pre className="whitespace-pre-wrap font-mono text-xs text-muted">
                          {detailsText(task.details)}
                        </pre>
                      </td>
                      <td className="py-4">
                        <AdminStatusChip status={task.status} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="border-t border-mist py-8">
        <h2 className="eyebrow">20 newest audit events</h2>
        {auditEvents.length === 0 ? (
          <p className="mt-4 text-sm text-muted">No audit events.</p>
        ) : (
          <ol className="mt-4 divide-y divide-mist border-y border-mist">
            {auditEvents.map((event) => {
              const occurred = adminDate(event.occurred_at);
              return (
                <li key={event.id} className="grid gap-2 py-4 text-sm sm:grid-cols-[11rem_1fr]">
                  <time dateTime={occurred.iso} className="text-xs text-muted">
                    {occurred.label}
                  </time>
                  <div>
                    <p className="text-river">
                      <span className="font-medium">{event.actor}</span> — {event.action}
                    </p>
                    <p className="mt-1 font-mono text-xs text-faint">
                      {event.entity_type} · {event.entity_id}
                    </p>
                    {event.before !== null || event.after !== null ? (
                      <details className="mt-2 text-xs text-muted">
                        <summary>Change details</summary>
                        <pre className="mt-2 whitespace-pre-wrap font-mono">
                          {detailsText({ before: event.before, after: event.after })}
                        </pre>
                      </details>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </section>
    </main>
  );
}
