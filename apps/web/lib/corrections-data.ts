import { query } from "@/lib/db";
import { getPublishedSnapshotId } from "@/lib/directory";
import { correctionDetails, type CorrectionSubmission } from "@/lib/corrections-model";

/** Resolve a slug only within the snapshot currently published to the web. */
export async function resolveCorrectionOrganizationId(orgSlug?: string): Promise<string | null> {
  if (!orgSlug) return null;
  const snapshotId = await getPublishedSnapshotId();
  if (!snapshotId) return null;

  const rows = await query<{ organization_id: string }>(
    `SELECT organization_id
       FROM read.org_directory
      WHERE snapshot_id = $1 AND slug = $2
      LIMIT 1`,
    [snapshotId, orgSlug]
  );
  return rows[0]?.organization_id ?? null;
}

export async function insertCorrectionSubmission(
  submission: CorrectionSubmission,
  organizationId: string | null
): Promise<void> {
  await query(
    `INSERT INTO app.correction_submission
       (organization_id, submitter_email, message, details)
     VALUES ($1, $2, $3, $4::jsonb)`,
    [
      organizationId,
      submission.submitter_email ?? null,
      submission.message,
      JSON.stringify(correctionDetails(submission))
    ]
  );
}
