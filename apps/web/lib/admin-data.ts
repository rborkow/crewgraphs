import { adminQuery } from "@/lib/admin-db";
import {
  parseDatabaseCount,
  type AdminAuditEventRow,
  type AdminCorrectionRow,
  type AdminCounts,
  type AdminReviewTaskRow
} from "@/lib/admin-model";

export async function getAdminCounts(): Promise<AdminCounts> {
  const [correctionRows, reviewRows] = await Promise.all([
    adminQuery<{ count: string | number }>(
      "SELECT COUNT(*)::text AS count FROM app.correction_submission WHERE status = $1",
      ["pending"]
    ),
    adminQuery<{ count: string | number }>(
      "SELECT COUNT(*)::text AS count FROM admin_v.review_task WHERE status = $1",
      ["open"]
    )
  ]);

  return {
    pendingCorrections: parseDatabaseCount(correctionRows[0]?.count),
    openReviewTasks: parseDatabaseCount(reviewRows[0]?.count)
  };
}

export async function getAdminCorrections(): Promise<AdminCorrectionRow[]> {
  return adminQuery<AdminCorrectionRow>(
    `SELECT c.id,
            c.created_at,
            c.organization_id,
            d.display_name AS org_display_name,
            d.slug AS org_slug,
            c.message,
            c.details,
            c.status
       FROM app.correction_submission c
       LEFT JOIN LATERAL (
         SELECT display_name, slug
           FROM read.org_directory
          WHERE organization_id = c.organization_id
          ORDER BY created_at DESC
          LIMIT 1
       ) d ON true
      ORDER BY c.created_at DESC`
  );
}

export async function getAdminReviewTasks(): Promise<AdminReviewTaskRow[]> {
  return adminQuery<AdminReviewTaskRow>(
    `SELECT id,
            entity_type,
            entity_id,
            task_type,
            status,
            assigned_to,
            details,
            created_at
       FROM admin_v.review_task
      ORDER BY CASE status
                 WHEN 'open' THEN 0
                 WHEN 'in_progress' THEN 1
                 ELSE 2
               END,
               created_at DESC`
  );
}

export async function getNewestAdminAuditEvents(): Promise<AdminAuditEventRow[]> {
  return adminQuery<AdminAuditEventRow>(
    `SELECT id,
            actor,
            action,
            entity_type,
            entity_id,
            before,
            after,
            reversal_of_event_id,
            occurred_at
       FROM admin_v.audit_event
      ORDER BY occurred_at DESC
      LIMIT 20`
  );
}
