import { query } from "@/lib/db";
import { getPublishedSnapshotId } from "@/lib/directory";
import {
  groupRegattaActivity,
  type RegattaResultRow,
  type SeasonBlock
} from "@/lib/regatta-read-model";

/**
 * Regatta-activity read for a profile page: the org's published results from
 * `read.org_regatta_result`, snapshot-scoped and regrouped for display.
 * Returns [] when the table has no rows for the org (no curated club links
 * yet, or the org simply has no ingested results) — the section renders its
 * coming-soon state. Tolerates the table not existing yet (migration 017 not
 * applied) so the web tier can deploy ahead of the publish side.
 */
export async function getRegattaActivity(slug: string): Promise<SeasonBlock[]> {
  const snapshotId = await getPublishedSnapshotId();
  if (!snapshotId) return [];

  try {
    const rows = await query<RegattaResultRow>(
      `SELECT r.season, r.regatta_key, r.regatta_name, r.regatta_date::text,
              r.venue, r.source_key, r.event_key, r.event_name, r.boat_class,
              r.round, r.crew_label, r.crew, r.metric_key, r.status, r.source_ref
         FROM read.org_regatta_result r
         JOIN read.org_directory d
           ON d.snapshot_id = r.snapshot_id AND d.organization_id = r.organization_id
        WHERE r.snapshot_id = $1 AND d.slug = $2
        ORDER BY r.season DESC, r.regatta_date DESC NULLS LAST, r.event_key, r.crew_label`,
      [snapshotId, slug]
    );
    return groupRegattaActivity(rows);
  } catch (error) {
    if (error instanceof Error && /org_regatta_result.*does not exist/i.test(error.message)) {
      return [];
    }
    throw error;
  }
}
