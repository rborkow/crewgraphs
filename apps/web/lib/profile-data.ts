import type { OrgProfilePayload } from "@crewgraphs/contracts";
import { query } from "@/lib/db";
import {
  groupTrends,
  mapProfilePayload,
  resolveFromRows,
  type FinancialSeriesRow,
  type SlugHistoryRow,
  type SlugResolution,
  type TrendChart,
  type Trends
} from "@/lib/read-model";
import { getPublishedSnapshotId } from "@/lib/directory";

/**
 * Profile read-model access. This is the seam the page components consume; the
 * component-facing types (Trends, SlugResolution, …) and `provenanceKey` are
 * re-exported unchanged so nothing above this module knows the data now comes
 * from Postgres (via the Hyperdrive binding) rather than fixtures.
 *
 * Every query filters on the single published snapshot id and is parameterized.
 * Payloads are parsed through the shared contract at the boundary (the contract
 * is the gate): an invalid payload throws rather than rendering.
 */

// Re-export the component-facing shapes so nothing above this seam needs to
// know they originate in the read-model module. (`provenanceKey` intentionally
// stays in the db-free read-model module — client components import it there.)
export type { Trends, TrendChart, SlugResolution };

/**
 * Resolve an incoming slug against the published directory + slug history:
 * a current page, a permanent-redirect target for a renamed org's old slug,
 * or a 404.
 */
export async function resolveSlug(slug: string): Promise<SlugResolution> {
  const snapshotId = await getPublishedSnapshotId();
  if (!snapshotId) return { kind: "not_found" };

  const [directoryRows, historyRows] = await Promise.all([
    query<{ organization_id: string; slug: string }>(
      "SELECT organization_id, slug FROM read.org_directory WHERE snapshot_id = $1",
      [snapshotId]
    ),
    query<SlugHistoryRow>(
      "SELECT slug, org_id, is_current FROM read.org_slug_history WHERE snapshot_id = $1",
      [snapshotId]
    )
  ]);

  return resolveFromRows(slug, directoryRows, historyRows);
}

/** The org profile payload for a current slug, or null when there is none. */
export async function getProfile(slug: string): Promise<OrgProfilePayload | null> {
  const snapshotId = await getPublishedSnapshotId();
  if (!snapshotId) return null;

  const rows = await query<{ payload: unknown }>(
    `SELECT p.payload
       FROM read.org_profile p
       JOIN read.org_directory d
         ON d.snapshot_id = p.snapshot_id AND d.organization_id = p.organization_id
      WHERE p.snapshot_id = $1 AND d.slug = $2`,
    [snapshotId, slug]
  );
  if (rows.length === 0) return null;
  return mapProfilePayload(rows[0].payload);
}

/**
 * Financial-trend charts + the chart-point provenance map for an org. Returns
 * empty charts when the org has no chartable series (e.g. a 990-N-only filer);
 * the caller renders the coverage explainer instead of an empty chart. Coverage
 * comes from the profile payload so injected missing-year gaps stay legible.
 */
export async function getTrends(slug: string): Promise<Trends> {
  const snapshotId = await getPublishedSnapshotId();
  if (!snapshotId) return { charts: [], provenance: {} };

  const rows = await query<{ payload: unknown } & Record<string, unknown>>(
    `SELECT p.payload, d.organization_id
       FROM read.org_profile p
       JOIN read.org_directory d
         ON d.snapshot_id = p.snapshot_id AND d.organization_id = p.organization_id
      WHERE p.snapshot_id = $1 AND d.slug = $2`,
    [snapshotId, slug]
  );
  if (rows.length === 0) return { charts: [], provenance: {} };

  const organizationId = rows[0].organization_id as string;
  const payload = mapProfilePayload(rows[0].payload);

  const seriesRows = await query<FinancialSeriesRow>(
    `SELECT series_key, tax_year, value, quality_state, is_amended, source_ref
       FROM read.org_financial_series
      WHERE snapshot_id = $1
        AND organization_id = $2
        AND series_key IN ('total_revenue', 'total_expenses')
      ORDER BY series_key, tax_year`,
    [snapshotId, organizationId]
  );

  return groupTrends(seriesRows, payload.coverage);
}
