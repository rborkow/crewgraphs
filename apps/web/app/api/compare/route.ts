import { getDirectory } from "@/lib/directory";
import { getCompareSeries } from "@/lib/compare-data";
import {
  buildCompareCsvRows,
  deriveComparisonYear,
  parseOrgSlugs,
  parseTaxYear,
  resolveComparisonSelection,
  serializeCompareCsv
} from "@/lib/compare-model";

export const dynamic = "force-dynamic";

export async function GET(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const parsedSlugs = parseOrgSlugs(url.searchParams.get("orgs"));
  const explicitYear = parseTaxYear(url.searchParams.get("fy"));
  const directory = await getDirectory();
  const selection = resolveComparisonSelection(directory.entries, parsedSlugs.slugs);
  const yearState = deriveComparisonYear(selection.organizations, explicitYear);

  const seriesRows =
    selection.organizations.length >= 2 && yearState.selectedYear !== null
      ? await getCompareSeries(
          directory.snapshot_id,
          selection.organizations.map((organization) => organization.org_id),
          yearState.selectedYear
        )
      : [];
  const csv = serializeCompareCsv(buildCompareCsvRows(seriesRows, selection.organizations));

  return new Response(csv, {
    headers: {
      "content-type": "text/csv; charset=utf-8",
      "content-disposition": `attachment; filename="crewgraphs-compare${yearState.selectedYear ? `-fy${yearState.selectedYear}` : ""}.csv"`
    }
  });
}
