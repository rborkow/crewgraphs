import {
  directoryBlobSchema,
  orgProfilePayloadSchema,
  type DirectoryBlob,
  type OrgProfilePayload
} from "@crewgraphs/contracts";
import { groupTrends, type FinancialSeriesRow, type Trends } from "@/lib/read-model";

import directoryJson from "../../../db/fixtures/directory.json";
import seriesJson from "../../../db/fixtures/series.json";

import bayward from "../../../db/fixtures/payloads/bayward-community-rowing.json";
import blueHeron from "../../../db/fixtures/payloads/blue-heron-community-oars.json";
import cedarPoint from "../../../db/fixtures/payloads/cedar-point-barge-club.json";
import cobalt from "../../../db/fixtures/payloads/cobalt-reach-club.json";
import harborview from "../../../db/fixtures/payloads/harborview-scholastic-oars.json";
import juniper from "../../../db/fixtures/payloads/juniper-creek-rowing.json";
import larkspur from "../../../db/fixtures/payloads/larkspur-river-adaptive.json";
import millbrook from "../../../db/fixtures/payloads/millbrook-community-rowing.json";
import northfield from "../../../db/fixtures/payloads/northfield-masters-rowing.json";
import pineglass from "../../../db/fixtures/payloads/pineglass-collegiate-club.json";
import redstone from "../../../db/fixtures/payloads/redstone-river-collective.json";
import silverplain from "../../../db/fixtures/payloads/silverplain-river-collective.json";

/**
 * Offline test fixtures. These are the db/fixtures payloads — the same shapes
 * the published read model emits — parsed through the shared contract so tests
 * exercise the real component/mapper code paths without ever opening a
 * connection. Nothing here touches lib/db.
 */

const RAW_PAYLOADS: unknown[] = [
  bayward,
  blueHeron,
  cedarPoint,
  cobalt,
  harborview,
  juniper,
  larkspur,
  millbrook,
  northfield,
  pineglass,
  redstone,
  silverplain
];

export const fixtureDirectory: DirectoryBlob = directoryBlobSchema.parse(directoryJson);

const PAYLOADS = new Map<string, OrgProfilePayload>(
  RAW_PAYLOADS.map((raw) => {
    const payload = orgProfilePayloadSchema.parse(raw);
    return [payload.slug, payload] as const;
  })
);

/** A parsed fixture profile payload by slug. */
export function fixturePayload(slug: string): OrgProfilePayload {
  const payload = PAYLOADS.get(slug);
  if (!payload) throw new Error(`no fixture payload for ${slug}`);
  return payload;
}

const SERIES = seriesJson as unknown as Record<string, FinancialSeriesRow[]>;

/** The raw fixture financial-series rows for a slug (DB-row shaped). */
export function fixtureSeriesRows(slug: string): FinancialSeriesRow[] {
  return SERIES[slug] ?? [];
}

/** Trends built from the fixture series + payload coverage, via the real mapper. */
export function fixtureTrends(slug: string): Trends {
  return groupTrends(fixtureSeriesRows(slug), fixturePayload(slug).coverage);
}
