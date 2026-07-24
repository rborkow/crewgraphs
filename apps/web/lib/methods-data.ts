import { query } from "@/lib/db";
import { getPublishedSnapshotId } from "@/lib/directory";
import {
  mapMetricCatalog,
  mapSourceRegistry,
  type MetricCatalogEntry,
  type SourceRegistryEntry
} from "@/lib/methods-model";

/**
 * Read-model access for /methods. Mirrors the profile-data seam: every query
 * filters on the single published snapshot id, payloads are validated through
 * the methods-model schemas at the boundary, and pages consume only the
 * validated shapes. No published snapshot renders as empty catalogs — the
 * static methodology prose never depends on the database.
 */

export async function getMetricCatalog(): Promise<MetricCatalogEntry[]> {
  const snapshotId = await getPublishedSnapshotId();
  if (!snapshotId) return [];

  const rows = await query<{ payload: unknown }>(
    `SELECT payload
       FROM read.metric_catalog
      WHERE snapshot_id = $1
      ORDER BY metric_key, metric_version`,
    [snapshotId]
  );
  return mapMetricCatalog(rows.map((row) => row.payload));
}

export async function getSourceRegistry(): Promise<SourceRegistryEntry[]> {
  const snapshotId = await getPublishedSnapshotId();
  if (!snapshotId) return [];

  const rows = await query<{ source_key: string; payload: unknown }>(
    `SELECT source_key, payload
       FROM read.source_registry_public
      WHERE snapshot_id = $1
      ORDER BY source_key`,
    [snapshotId]
  );
  return mapSourceRegistry(rows);
}
