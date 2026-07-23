import { query } from "@/lib/db";
import { COMPARISON_SERIES_KEYS, type CompareSeriesRow } from "@/lib/compare-model";

/** Fetch all requested comparison cells for one IRS TaxYr in one query. */
export async function getCompareSeries(
  snapshotId: string,
  organizationIds: string[],
  taxYear: number
): Promise<CompareSeriesRow[]> {
  if (organizationIds.length === 0) return [];

  return query<CompareSeriesRow>(
    `SELECT organization_id,
            series_key,
            series_version,
            tax_year,
            fiscal_year_end,
            value,
            quality_state,
            is_amended,
            source_ref
       FROM read.org_financial_series
      WHERE snapshot_id = $1
        AND organization_id = ANY($2::uuid[])
        AND tax_year = $3
        AND series_key = ANY($4::text[])
      ORDER BY organization_id, series_key, series_version`,
    [
      snapshotId,
      `{${organizationIds.join(",")}}`,
      taxYear,
      `{${COMPARISON_SERIES_KEYS.join(",")}}`
    ]
  );
}
