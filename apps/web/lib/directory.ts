import type { DirectoryBlob } from "@crewgraphs/contracts";
import { query } from "@/lib/db";
import {
  assembleDirectory,
  buildDataThroughLabel,
  type DirectoryJoinRow,
  type PublishedSnapshotRow
} from "@/lib/read-model";

/**
 * Directory read-model access + publish metadata. The published directory is
 * assembled live from `read.org_directory` joined with each org's profile
 * payload, then validated entry-by-entry through the shared contract. In
 * production the query runs against Neon through the Hyperdrive binding; in
 * `next dev` it runs against the local read replica.
 *
 * Every query filters on the single published snapshot id.
 */

/** The single published snapshot id, or null if nothing has been published. */
export async function getPublishedSnapshotId(): Promise<string | null> {
  const rows = await query<{ snapshot_id: string }>(
    "SELECT snapshot_id FROM read.published_snapshot WHERE singleton = true LIMIT 1"
  );
  return rows[0]?.snapshot_id ?? null;
}

/** The publish metadata the site + sources footers render. */
export interface PublishMeta {
  snapshot_id: string;
  published_at: string;
  data_through_label: string;
}

async function fetchSnapshot(): Promise<PublishedSnapshotRow | null> {
  const rows = await query<PublishedSnapshotRow>(
    "SELECT snapshot_id, updated_at FROM read.published_snapshot WHERE singleton = true LIMIT 1"
  );
  return rows[0] ?? null;
}

/**
 * Publish metadata only (no entries) — a lightweight read for the footers,
 * which need the data-through label and the publish date but not the roster.
 */
export async function getPublishMeta(): Promise<PublishMeta | null> {
  // Rendered from the root layout, including build-time prerenders of error
  // pages: an unreachable database must degrade to "no freshness line",
  // never prevent a page (or the 404 page) from rendering.
  let snapshot: Awaited<ReturnType<typeof fetchSnapshot>>;
  try {
    snapshot = await fetchSnapshot();
  } catch {
    return null;
  }
  if (!snapshot) return null;
  const publishedAt =
    snapshot.updated_at instanceof Date ? snapshot.updated_at.toISOString() : snapshot.updated_at;
  return {
    snapshot_id: snapshot.snapshot_id,
    published_at: publishedAt,
    data_through_label: buildDataThroughLabel(snapshot.updated_at)
  };
}

/** The full published directory blob: publish metadata + validated entries. */
export async function getDirectory(): Promise<DirectoryBlob> {
  const snapshot = await fetchSnapshot();
  if (!snapshot) {
    throw new Error("No published snapshot: read.published_snapshot has no singleton row.");
  }

  const rows = await query<DirectoryJoinRow>(
    `SELECT d.organization_id,
            d.slug,
            d.display_name,
            d.aliases,
            d.coverage_state,
            d.fye_month,
            p.payload
       FROM read.org_directory d
       JOIN read.org_profile p
         ON p.snapshot_id = d.snapshot_id AND p.organization_id = d.organization_id
      WHERE d.snapshot_id = $1
      ORDER BY d.display_name`,
    [snapshot.snapshot_id]
  );

  return assembleDirectory(snapshot, rows);
}
